# -*- coding: utf-8 -*-
"""通过 app 真实事件函数走完整 Mock 流程（操作 app.state）"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import app

script = app.load_example_script()
actors = app.load_example_actors()
print("示例剧本长度:", len(script), "| 示例演员材料长度:", len(actors))

# 1. 角色蒸馏
md_role, json_role, role_dd, target_dd = app.distill_roles(script)
print("\n角色数:", len(app.state.role_cards))
for r in app.state.role_cards:
    print("  -", r.role_name, "| 可观察要求:", len(r.casting_guide.observable_requirements))

# 2. 演员观察（对照第一个角色）
first_role = app.state.role_cards[0].role_name
print("\n对照角色:", first_role)
md_actor, json_actor = app.profile_actors(actors, first_role)
print("演员数:", len(app.state.actor_profiles))
for p in app.state.actor_profiles:
    print(f"  - {p.actor_name} | status={p.analysis_status} | 观察={len(p.observations)} 待验证={len(p.verification_items)}")

# 3. 全量候选方案
md_match, json_match = app.run_full_matching()
for rr in app.state.casting_report.results:
    print(f"\n角色「{rr.role_name}」:")
    for p in rr.proposals:
        contradicted = sum(1 for c in p.evidence_comparisons if c.evidence_status == "contradicted")
        supported = sum(1 for c in p.evidence_comparisons if c.evidence_status == "supported")
        missing = sum(1 for c in p.evidence_comparisons if c.evidence_status == "missing")
        print(f"   {p.category:22s} {p.actor_name} | 支持{supported} 缺失{missing} 相反{contradicted}")
    if rr.chemistry_checks:
        print("   化学反应建议:", rr.chemistry_checks)

print("\n全局说明:", app.state.casting_report.global_notes)
print("\n✅ app 真实流程测试完成")
