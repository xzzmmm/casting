# -*- coding: utf-8 -*-
"""
DramaScheduler · FastAPI 后端
=============================
上传 NA 表（Excel/CSV，模板 v2 结构）→ 解析成员信息 → 派生排练任务
→ CP-SAT 求解 → 返回日程 JSON。

启动：uvicorn main:app --host 127.0.0.1 --port 8000  （在本目录下）
页面：http://127.0.0.1:8000
"""
import io
import json
import re
import os

# 注意：scheduler 会加载 ortools 的 DLL，必须在 pandas/fastapi 之前导入。
# conda 的 pandas 先加载自身 DLL 会污染搜索路径，导致 ortools WinDLL 加载失败（WinError 127）。
from scheduler import solve as solve_core
import real_na_parser

import pandas as pd
from fastapi import FastAPI, File, Form, Response, UploadFile
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="DramaScheduler API", version="0.1")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ---------------------------------------------------------------------------
# 默认任务模板：由成员的"参与任务（场次）"标签派生演员
# ---------------------------------------------------------------------------
DEFAULT_TASKS = [
    {"id": "R1", "name": "《雷雨》一幕", "tags": ["全剧", "一幕"],
     "dur": 2, "req": 3, "prio": 3},
    {"id": "R2", "name": "《雷雨》二幕", "tags": ["全剧", "二幕"],
     "dur": 2, "req": 3, "prio": 2},
    {"id": "R3", "name": "《雷雨》三幕", "tags": ["全剧", "三幕"],
     "dur": 2, "req": 2, "prio": 2},
    {"id": "R4", "name": "走位彩排（全员）", "tags": ["全员"],
     "dur": 1, "req": 1, "prio": 1},
    {"id": "R5", "name": "技术联排（灯光/场务）", "tags": ["全剧", "技术联排"],
     "dur": 1, "req": 1, "prio": 1},
]

SLOT_RE = re.compile(r"^周[一二三四五六日][早晚午]$")


def parse_na_table(content: bytes, filename: str):
    """解析上传的 NA 表（模板 v2：A-E 个人信息 + F-Z 时段矩阵）"""
    if filename.lower().endswith((".xlsx", ".xls")):
        df = pd.read_excel(io.BytesIO(content))
    else:
        raw = content.decode("utf-8-sig", errors="replace")
        df = pd.read_csv(io.StringIO(raw), dtype=str)
    df = df.dropna(how="all").dropna(axis=1, how="all")
    df.columns = [str(c).strip() for c in df.columns]

    # 定位时段列与信息列
    time_cols = [c for c in df.columns if SLOT_RE.match(c)]
    if not time_cols:
        raise ValueError("未识别到时序列（列名应为 周一早/周一午/… 格式）")
    if "成员姓名" not in df.columns:
        raise ValueError("缺少『成员姓名』列，请使用模板 v2 结构上传")

    info_cols = {c: c for c in ["职位/角色", "所属组别", "参与任务（场次）", "关键人物"]
                 if c in df.columns}
    members, na_count = [], 0
    for _, row in df.iterrows():
        name = str(row["成员姓名"]).strip()
        if not name or name.lower() in ("nan", "none"):
            continue
        tasks_raw = str(row.get("参与任务（场次）", "") or "")
        key_raw = str(row.get("关键人物", "") or "").strip()
        na_idx = []
        for i, col in enumerate(time_cols):
            v = str(row.get(col, "")).strip().upper()
            if v == "NA" or (v and v != "V"):
                na_idx.append(i)
                na_count += 1
        members.append({
            "name": name,
            "role": str(row.get("职位/角色", "") or "").strip(),
            "group": str(row.get("所属组别", "") or "").strip(),
            "tasks": [t for t in re.split(r"[·、,，/]", tasks_raw) if t.strip()],
            "key": key_raw == "是",
            "na_indices": na_idx,
        })
    if not members:
        raise ValueError("未解析到任何成员，请检查表格内容")
    return members, time_cols, na_count


def derive_actors(tasks_cfg, members):
    """根据任务标签派生演员清单；无标签的任务保留调用方传入的 actors"""
    name_set = {m["name"] for m in members}
    for t in tasks_cfg:
        tags = t.get("tags") or []
        if "全员" in tags:
            actors = sorted(name_set)
        elif tags:
            tags_set = set(tags)
            # 匹配规则：成员"参与任务"含任务任一标签；或成员为"全剧·必到"且任务带"全剧"标签
            actors = sorted(m["name"] for m in members
                            if (tags_set & set(m["tasks"]))
                            or ("全剧" in tags_set and "全剧" in set(m["tasks"])))
        else:
            actors = t.get("actors") or []   # 前端已指定演员（如自定义任务）
        t["actors"] = actors
    return tasks_cfg


# ---------------------------------------------------------------------------
# 真实 NA 表（日期×时段结构）处理
# ---------------------------------------------------------------------------
CORE_ROLES = ("导演", "舞监", "ASM", "制作人")
TECH_ROLES = CORE_ROLES + ("灯光", "舞美", "服装", "音响")


def _match_members(roles, members):
    """按成员注明的职位匹配必到人员。"""
    return sorted(m["name"] for m in members if any(r in m["role"].upper() for r in roles))


def build_real_members(data):
    """真实格式 -> members（含 role / key / na_indices）"""
    members = []
    for m in data["members"]:
        name = m["name"]
        role = name.split("-", 1)[1].strip() if "-" in name else ""
        na_idx = []
        for idx, s in enumerate(data["slots"]):
            v = (data["avail"][name].get(s["col"]) or "").strip()
            if v.upper() == "NA" or "未知" in v:
                na_idx.append(idx)
        members.append({
            "name": name, "role": role, "group": "",
            "tasks": [], "key": any(r in role.upper() for r in CORE_ROLES),
            "na_indices": na_idx,
        })
    return members


def build_real_slots(data):
    """真实格式 -> slots=[{label, day, part}]（按日期+时段排序）"""
    slots = []
    for s in data["slots"]:
        m = re.match(r"\d{4}/(\d+/\d+)（(.*?)）", s["date"])
        day = (m.group(1) + " " + m.group(2)) if m else s["date"]
        slots.append({"label": day + " " + s["session"], "day": day, "part": s["session"]})
    return slots


def build_real_tasks(members):
    """真实格式默认任务：
    actors = 表中标注的必到主创（导演+舞监+ASM+制作人）
    soft_actors = 其余成员（尽量到场，软激励）
    R4 技术合成为导演+舞监+灯光/舞美/服装 必到。
    """
    all_names = {m["name"] for m in members}
    hard = _match_members(CORE_ROLES, members)
    hard_tech = _match_members(TECH_ROLES, members)
    soft_all = sorted(all_names - set(hard))
    soft_tech = sorted(all_names - set(hard_tech))
    return [
        {"id": "R1", "name": "剧本围读（主创必到）", "dur": 4, "req": 1, "prio": 3,
         "actors": hard, "soft_actors": soft_all},
        {"id": "R2", "name": "Blocking 排练（分幕走位）", "dur": 4, "req": 1, "prio": 2,
         "actors": hard, "soft_actors": soft_all},
        {"id": "R3", "name": "走位彩排（主创必到）", "dur": 3, "req": 1, "prio": 1,
         "actors": hard, "soft_actors": soft_all},
        {"id": "R4", "name": "舞台技术合成（灯光/舞美/服装）", "dur": 3, "req": 1, "prio": 1,
         "actors": hard_tech, "soft_actors": soft_tech},
        {"id": "R5", "name": "演出前联排（主创必到）", "dur": 4, "req": 1, "prio": 1,
         "actors": hard, "soft_actors": soft_all},
    ]


# 最近一次成功排期结果（供 /api/export 导出 CSV，前端 blob 下载在部分客户端被拦截）
_LAST_RESULT = None


@app.post("/api/schedule")
async def api_schedule(file: UploadFile = File(...),
                       max_day_dur: float = Form(4.0),
                       tasks_json: str = Form("")):
    """上传 NA 表 → 排期 → 返回日程 JSON

    自动识别两种格式：
    - 模板 v2：A-E 个人信息 + 周一早…周日 晚 时段矩阵
    - 真实 NA 表：日期×时段 结构（9/12 19:00-23:00 …），支持部分出席标记近似处理
    """
    global _LAST_RESULT
    content = await file.read()

    # 1) 尝试模板 v2（pandas 可读时）
    mode, members, slots, time_cols, na_count, parse_extra = "v2", None, None, [], 0, {}
    try:
        members, time_cols, na_count = parse_na_table(content, file.filename)
    except Exception:
        # 2) 回退真实格式（zipfile/XML 解析，兼容 openpyxl 读不了的文件）
        try:
            data = real_na_parser.parse_real_na_bytes(content)
        except Exception:
            return {"ok": False, "error": "无法解析文件：请上传模板 v2 结构或真实 NA 表（.xlsx）"}
        members = build_real_members(data)
        slots = build_real_slots(data)
        time_cols = [s["label"] for s in slots]
        na_count = sum(len(m["na_indices"]) for m in members)
        mode = "real"
        parse_extra = {"partial_count": sum(len(v) for v in data["partial"].values()),
                       "partial_members": len(data["partial"]),
                       "suggest_day_dur": 8}

    tasks_cfg = json.loads(tasks_json) if tasks_json.strip() else None
    if tasks_cfg is None:
        tasks_cfg = build_real_tasks(members) if mode == "real" else [task.copy() for task in DEFAULT_TASKS]
    try:
        tasks_cfg = derive_actors(tasks_cfg, members)
    except Exception as e:  # 用户自定义任务格式异常时回退默认
        fallback = build_real_tasks(members) if mode == "real" else [task.copy() for task in DEFAULT_TASKS]
        tasks_cfg = derive_actors(fallback, members)

    kw = {}
    if slots:
        kw["slots"] = slots
    result = solve_core(members, tasks_cfg, max_day_dur=float(max_day_dur), **kw)
    result["parse"] = {
        "mode": mode,
        "members_count": len(members),
        "time_cols": len(time_cols),
        "na_count": na_count,
        "tasks_count": len(tasks_cfg),
        "tasks": [{"id": t["id"], "name": t["name"], "dur": t["dur"],
                   "req": t["req"], "prio": t["prio"], "actors": t["actors"],
                   "soft": t.get("soft_actors", [])}
                  for t in tasks_cfg],
    }
    result["parse"].update(parse_extra)
    result["params"] = {"max_day_dur": float(max_day_dur)}
    if result.get("ok"):
        _LAST_RESULT = result
    return result


@app.get("/api/export")
async def export_csv():
    """导出最近一次排期结果为 CSV（附件下载，文件名含日期）"""
    res = _LAST_RESULT
    if not res or not res.get("ok"):
        return {"ok": False, "error": "暂无排期结果，请先完成一次排期"}
    rows = ["日期,时段,任务,时长(小时),参演人员"]
    for r in res["schedule"]:
        day = r.get("day", r.get("slot_name", ""))
        part = r.get("slot_part", r.get("slot_time", ""))
        name = r.get("task_name", "")
        dur = r.get("dur", "")
        actors = "、".join(r.get("actors", []) or [])
        rows.append(",".join('"' + str(c).replace('"', '""') + '"' for c in (day, part, name, dur, actors)))
    body = "\n".join(rows) + "\n"
    from datetime import date
    from urllib.parse import quote
    fname = f"排练日程_{date.today().isoformat()}.csv"
    return Response(
        content=body.encode("utf-8-sig"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition":
                 f"attachment; filename*=UTF-8''{quote(fname)}"},
    )


@app.get("/api/health")
async def health():
    return {"ok": True, "service": "DramaScheduler"}


# 静态前端（index.html）—— 必须在 API 路由之后挂载，避免吞掉 /api/* 请求
app.mount("/", StaticFiles(directory=os.path.join(BASE_DIR, "static"), html=True), name="static")


# 便捷入口：允许 `python main.py` 直接启动
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
