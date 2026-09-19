# -*- coding: utf-8 -*-
"""CastingNuwa v0.6 端到端流程测试（Mock 模式，不依赖真实 API）。"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import app  # noqa: E402

ROOT = os.path.dirname(os.path.abspath(__file__))


def read_example(name):
    with open(os.path.join(ROOT, "examples", name), "r", encoding="utf-8") as f:
        return f.read()


def assert_true(cond, msg):
    if not cond:
        raise AssertionError(msg)
    print("  PASS:", msg)


print("== 1. 角色蒸馏 ==")
state = None
script = read_example("sample_script.txt")
out = app.distill_roles(state, script)
state = out[0]
assert_true(len(state.role_cards) >= 2, f"蒸馏出 {len(state.role_cards)} 个角色（>=2）")
first_role = state.role_names()[0]

print("== 2. 未确认设定时，全量候选应被拦截 ==")
actors_text = read_example("sample_actors.txt")
pout = app.profile_actors(state, actors_text, first_role, "", "", "")
state = pout[0]
assert_true(len(state.actor_profiles) >= 2, f"记录 {len(state.actor_profiles)} 位演员")
blocked = app.run_full_matching(state)
assert_true("选角设定" in blocked[1], "未确认设定时给出拦截提示")
assert_true(blocked[0].casting_report is None, "拦截时不生成报告")

print("== 3. 预填 + 保存确认选角设定 ==")
pf = app.prefill_settings(state)
state, must_text, rehearse_text, _ = pf
assert_true(must_text or rehearse_text, "从角色卡预填出可观察要求")
sout = app.save_settings(
    state, "克制写实", "聚焦人物不愿表露的情绪",
    must_text, rehearse_text, False, True, "每周三晚、周日全天排练",
)
state = sout[0]
assert_true(state.production_settings.confirmed, "设定已确认")
assert_true(state.production_settings.allow_double_casting, "允许兼角已记录")

print("== 4. 生成全部角色试镜任务 ==")
aout = app.design_all_auditions(state)
state = aout[0]
assert_true(len(state.audition_tasks) == len(state.role_cards),
            f"为 {len(state.audition_tasks)} 个角色生成试镜任务")
sample_task = next(iter(state.audition_tasks.values()))
assert_true(bool(sample_task.adjustment_instruction), "试镜任务含调整指令")
assert_true(bool(sample_task.retest_task), "试镜任务含复试任务")
assert_true(len(sample_task.observation_focus) >= 1, "试镜任务含观察重点")

print("== 5. 两轮复试 + 档期（单演员） ==")
single = (
    "【演员：复试测试员】\n"
    "第一遍：她停顿了很久，声音发抖但努力平静，眼眶泛红，没有看对方。\n"
)
adj = "这次你非常想让对方留下，但不能让对方察觉。"
second = "第二遍：她依然克制，但嘴角有一次极轻微的上扬，随即低下头，手攥紧了衣角。"
p2 = app.profile_actors(state, single, first_role, adj, second, "周三晚没空，周日可以")
state2 = p2[0]
tester = state2.actor_profiles[-1]
assert_true(tester.schedule_info == "周三晚没空，周日可以", "档期已记录且不参与演技判断")
assert_true(len(tester.adjustment_responses) >= 1 or any(
    "第二遍" in (o.timestamp or "") for o in tester.observations
), "记录了指导后复试信息")

print("== 6. 确认设定后全量候选 + 兼角/档期全局说明 ==")
mout = app.run_full_matching(state)
state = mout[0]
assert_true(state.casting_report is not None, "确认设定后生成候选报告")
assert_true(len(state.casting_report.results) == len(state.role_cards), "每个角色都有候选结果")

print("== 7. 人工确认最终人选并保存理由 ==")
result0 = state.casting_report.results[0]
role0 = result0.role_name
actor0 = result0.proposals[0].actor_name
actor_choices = [p.actor_name for p in result0.proposals]
dd = app.update_confirm_actors(state, role0)
cout = app.confirm_decision(state, role0, actor0, "复试后调整到位，对手戏需再验证")
state = cout[0]
assert_true(state.casting_report.get_result_for_role(role0).confirmed_actor_name == actor0,
            "最终人选已确认")
assert_true(actor0 in cout[1], "决定表显示确认人选")

print("== 8. 项目保存 → 加载往返 ==")
saved_path, _ = app.save_project(state)
assert_true(saved_path and os.path.exists(saved_path), f"项目文件已保存：{saved_path}")
loaded = app.load_project(None, saved_path)
loaded_state = loaded[0]
assert_true(len(loaded_state.role_cards) == len(state.role_cards), "加载后角色数一致")
assert_true(len(loaded_state.actor_profiles) == len(state.actor_profiles), "加载后演员数一致")
assert_true(loaded_state.production_settings.confirmed, "加载后设定确认状态保留")
assert_true(len(loaded_state.audition_tasks) == len(state.audition_tasks), "加载后试镜任务保留")
assert_true(loaded_state.casting_report is not None, "加载后候选报告保留")
assert_true(
    loaded_state.casting_report.get_result_for_role(role0).confirmed_actor_name == actor0,
    "加载后人工确认结果保留",
)
assert_true(loaded_state.crew_analysis is None, "未分析的团队项为空（不伪造）")

print("\n全部 v0.6 流程测试通过 ✅")
print("项目存档：", saved_path)
