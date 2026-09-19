# -*- coding: utf-8 -*-
"""v0.6 端到端冒烟：通过 app 事件函数走完整 Mock 流程（会话隔离签名）。"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import app

script = app.load_example_script()
actors = app.load_example_actors()
print("示例剧本长度:", len(script), "| 示例演员材料长度:", len(actors))

# 1. 角色蒸馏
state = None
out = app.distill_roles(state, script)
state = out[0]
print("\n角色数:", len(state.role_cards))
for r in state.role_cards:
    print("  -", r.role_name, "| 可观察要求:", len(r.casting_guide.observable_requirements))

# 2. 演员观察（对照第一个角色）
first_role = state.role_cards[0].role_name
print("\n对照角色:", first_role)
pout = app.profile_actors(state, actors, first_role, "", "", "")
state = pout[0]
print("演员数:", len(state.actor_profiles))
for p in state.actor_profiles:
    print(f"  - {p.actor_name} | status={p.analysis_status} | "
          f"观察={len(p.observations)} 待验证={len(p.verification_items)}")

# 3. 未确认设定时应被拦截
blocked = app.run_full_matching(state)
assert blocked[0].casting_report is None, "未确认设定不应生成报告"
print("\n未确认设定时已正确拦截：", blocked[1][:30])

# 4. 确认选角设定（允许兼角，便于回归兼角提示）
sout = app.save_settings(
    state, "克制写实", "聚焦不愿表露的情绪",
    "情绪克制但能让观众读懂\n", "肢体幅度可排练\n",
    False, True, "周日全天排练",
)
state = sout[0]

# 5. 全量候选方案
mout = app.run_full_matching(state)
state = mout[0]
assert state.casting_report is not None, "确认设定后应生成报告"

priority_actor = ""
needs_more_actor = ""
for rr in state.casting_report.results:
    print(f"\n角色「{rr.role_name}」:")
    for p in rr.proposals:
        contradicted = sum(1 for c in p.evidence_comparisons if c.evidence_status == "contradicted")
        supported = sum(1 for c in p.evidence_comparisons if c.evidence_status == "supported")
        missing = sum(1 for c in p.evidence_comparisons if c.evidence_status == "missing")
        print(f"   {p.category:22s} {p.actor_name} | 支持{supported} 缺失{missing} 相反{contradicted}")
        if rr.role_name == state.role_cards[0].role_name:
            if p.category == "priority_audition":
                priority_actor = p.actor_name
            if p.category == "needs_more_audition":
                needs_more_actor = p.actor_name
    if rr.chemistry_checks:
        print("   化学反应建议:", rr.chemistry_checks)

print("\n全局说明:", state.casting_report.global_notes)

# v0.5 调好的分类基线不可退化
assert priority_actor == "林晓雨", f"克制型林晓雨应优先试演，实际：{priority_actor}"
assert needs_more_actor == "张浩然", f"外放型张浩然应补充试镜，实际：{needs_more_actor}"
print("\n✅ app 真实流程测试完成，分类基线保持：林晓雨=优先试演，张浩然=补充试镜")
