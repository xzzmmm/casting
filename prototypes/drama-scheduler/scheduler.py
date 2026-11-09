# -*- coding: utf-8 -*-
"""
DramaScheduler · 排期核心模块（scheduler.py）
=============================================
从原型 drama_scheduler.py 重构出的可复用模块：
输入成员信息 + 任务清单 → CP-SAT 求解 → 结构化结果 dict。
供 FastAPI 后端调用，也可被单元测试/脚本直接 import。

支持两种时段结构：
- 默认：模板 v2 的 21 时段（周一早 … 周日晚）
- 自定义：真实 NA 表的「日期 × 时段」结构（如 9/12(六) 19:00-23:00）

运行环境：Python 3.10+，依赖 ortools（OR-Tools CP-SAT）。
"""
from ortools.sat.python import cp_model

SLOT_NAMES = [f"{d}{s}" for d in ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
              for s in ["早", "午", "晚"]]
N_SLOTS = len(SLOT_NAMES)          # 21
DAYS = [list(range(d * 3, d * 3 + 3)) for d in range(7)]
DAY_NAMES = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]


def _availability(members, n_slots):
    """成员 NA 集合 -> {name: 可用时段集合}"""
    return {m["name"]: {j for j in range(n_slots) if j not in set(m.get("na_indices", []))}
            for m in members}


def build_model(tasks, avail, max_day_dur, n_slots, day_groups, deadline=None):
    """构造 CP-SAT 模型，返回 (model, x, ends, max_end)

    Args:
        tasks:     任务清单 [{"id","actors","dur","req","prio"}]
        avail:     {成员名: 可用时段索引集合}
        n_slots:   时段总数
        day_groups: 按"天"分组的时段索引列表，如 [[0,1,2],[3,4,5],...]
        deadline:  最晚完成时段（默认 = n_slots，即不设限）
    """
    model = cp_model.CpModel()
    deadline = deadline or n_slots
    x = {i: {j: model.NewBoolVar(f"x_{t['id']}_s{j}") for j in range(n_slots)}
         for i, t in enumerate(tasks)}

    # 硬约束 1：可用性
    for i, t in enumerate(tasks):
        for j in range(n_slots):
            if not all(j in avail[a] for a in t["actors"]):
                model.Add(x[i][j] == 0)

    # 硬约束 2：一人一时段
    all_actors = {a for t in tasks for a in t["actors"]}
    for a in all_actors:
        for j in range(n_slots):
            model.Add(sum(x[i][j] for i, t in enumerate(tasks) if a in t["actors"]) <= 1)

    # 硬约束 3：任务覆盖
    for i, t in enumerate(tasks):
        model.Add(sum(x[i][j] for j in range(n_slots)) >= t["req"])

    # 硬约束 4：每日时长上限（CP-SAT 要求整数常量）
    max_day_dur_i = int(round(max_day_dur))
    for slots in day_groups:
        model.Add(sum(x[i][j] * t["dur"] for i, t in enumerate(tasks) for j in slots)
                  <= max_day_dur_i)

    # 硬约束 5：截止期
    ends = {}
    for i, t in enumerate(tasks):
        ends[i] = model.NewIntVar(0, n_slots - 1, f"end_{t['id']}")
        model.Add(ends[i] == sum(j * x[i][j] for j in range(n_slots)))
        model.Add(ends[i] <= deadline - 1)

    # 软目标：最小化完成周期 + 优先级加权；若任务带 soft_actors（软参与名单），
    # 奖励"排期时段该软参与者可用"（尽量让更多成员到场，但不硬约束）
    max_end = model.NewIntVar(0, n_slots - 1, "max_end")
    model.AddMaxEquality(max_end, [ends[i] for i in range(len(tasks))])
    soft_terms = []
    for i, t in enumerate(tasks):
        for a in t.get("soft_actors", []):
            for j in range(n_slots):
                if j in avail.get(a, set()):
                    soft_terms.append(x[i][j])
    model.Minimize(max_end * n_slots
                   + sum((j + 1) * x[i][j] * (4 - t["prio"])
                         for i, t in enumerate(tasks) for j in range(n_slots))
                   - sum(soft_terms))
    return model, x, ends, max_end


def solve(members, tasks, max_day_dur=4.0, time_limit=10.0, slots=None):
    """求解主入口。

    Args:
        members: [{"name", "role", "group", "tasks": [参与标签], "key": bool,
                   "na_indices": [不可用时段]}]
        tasks:   [{"id", "name", "actors": [成员名], "dur": 小时, "req": 次数,
                   "prio": 1-3}]
        max_day_dur: 每日排练时长上限（小时）
        slots:   可选。None = 默认 21 时段（周一早…周日晚）；
                 否则为 [{label, day, part}]，表示真实 NA 表的时段集合。
    Returns:
        dict: status / schedule / stats / conflicts / progress / max_end /
              time_sec / infeasible_hint
    """
    if slots is None:
        n_slots, day_groups = N_SLOTS, DAYS
        slot_names = SLOT_NAMES
        day_name_of = lambda j: DAY_NAMES[j // 3]
        part_of = lambda j: SLOT_NAMES[j][2:]
        progress_keys = DAY_NAMES
    else:
        n_slots = len(slots)
        order, groups = [], {}
        for idx, s in enumerate(slots):
            d = s["day"]
            if d not in groups:
                groups[d], order = [], order + [d]
            groups[d].append(idx)
        day_groups = [groups[d] for d in order]
        slot_names = [s["label"] for s in slots]
        day_name_of = lambda j: slots[j]["day"]
        part_of = lambda j: slots[j]["part"]
        progress_keys = order

    avail = _availability(members, n_slots)
    model, x, ends, max_end = build_model(tasks, avail, max_day_dur, n_slots, day_groups)
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit
    status = solver.Solve(model)
    ok = status in (cp_model.OPTIMAL, cp_model.FEASIBLE)

    if not ok:
        # 无解诊断：先尝试放宽每日时长上限
        hint = None
        for relax in (5, 6, 8):
            m2, _, _, _ = build_model(tasks, avail, relax, n_slots, day_groups)
            s2 = cp_model.CpSolver()
            if s2.Solve(m2) in (cp_model.OPTIMAL, cp_model.FEASIBLE):
                hint = {"type": "relax_day_limit", "suggest": relax}
                break
        if hint is None:
            # 再诊断：任务必到成员的公共空闲时段不足
            short = []
            for t in tasks:
                common = [j for j in range(n_slots)
                          if all(j in avail[a] for a in t["actors"])]
                if len(common) < t["req"]:
                    short.append({"task": t["name"], "req": t["req"],
                                  "available": len(common),
                                  "slots": [slot_names[j] for j in common]})
            if short:
                hint = {"type": "not_enough_common_slots", "detail": short}
        return {"ok": False, "status": solver.StatusName(status),
                "infeasible_hint": hint,
                "schedule": [], "stats": {}, "conflicts": [],
                "progress": [], "max_end": None, "time_sec": solver.WallTime()}

    schedule = []
    for i, t in enumerate(tasks):
        for j in range(n_slots):
            if solver.Value(x[i][j]) == 1:
                schedule.append({
                    "task_id": t["id"], "task_name": t["name"],
                    "slot": j, "slot_name": slot_names[j],
                    "day": day_name_of(j), "slot_part": part_of(j),
                    "dur": t["dur"], "actors": t["actors"],
                })
    schedule.sort(key=lambda r: r["slot"])

    stats = {}
    for r in schedule:
        for a in r["actors"]:
            stats[a] = stats.get(a, 0) + 1

    # 冲突自检（理论为 0，保留防线）
    conflicts, seen = [], {}
    for r in schedule:
        for a in r["actors"]:
            if (a, r["slot"]) in seen:
                conflicts.append({"actor": a, "slot": r["slot_name"],
                                  "with": seen[(a, r["slot"])], "task": r["task_id"]})
            seen[(a, r["slot"])] = r["task_id"]

    # 每日进度推进（按日期/星期分组）
    total_req = sum(t["req"] for t in tasks)
    done = [0] * len(progress_keys)
    idx_of_day = {d: k for k, d in enumerate(progress_keys)}
    for r in schedule:
        done[idx_of_day[r["day"]]] += 1
    cum, progress = 0, []
    for k, d in enumerate(progress_keys):
        cum += done[k]
        progress.append({"day": d, "count": done[k],
                         "cum": cum, "total": total_req,
                         "pct": round(cum / total_req * 100) if total_req else 0})

    return {
        "ok": True,
        "status": solver.StatusName(status),
        "time_sec": round(solver.WallTime(), 3),
        "max_end": solver.Value(max_end),
        "max_end_name": slot_names[solver.Value(max_end)],
        "schedule": schedule,
        "stats": stats,
        "conflicts": conflicts,
        "progress": progress,
        "total_req": total_req,
        "infeasible_hint": None,
    }
