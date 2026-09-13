"""
CastingNuwa 端到端验证脚本
测试完整工作流：角色蒸馏 → 演员画像 → 智能匹配 → 选角报告
"""
import os
import sys
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.role_distiller import RoleDistiller
from src.actor_profiler import ActorProfiler
from src.matching_engine import MatchingEngine
from src.llm_client import LLMClient


def main():
    print("=" * 60)
    print("  CastingNuwa 端到端验证")
    print("=" * 60)

    base = os.path.dirname(os.path.abspath(__file__))
    llm = LLMClient()

    # ========== Step 1: 角色蒸馏 ==========
    print("\n" + "=" * 60)
    print("  Step 1: 角色蒸馏")
    print("=" * 60)

    script_path = os.path.join(base, "examples", "sample_script.txt")
    with open(script_path, "r", encoding="utf-8") as f:
        script = f.read()

    distiller = RoleDistiller(llm_client=llm)
    role_cards = distiller.distill_all(script)

    assert len(role_cards) > 0, "角色蒸馏失败：未生成任何角色卡"
    for card in role_cards:
        assert card.role_name, "角色名为空"
        assert len(card.personality) > 0, f"{card.role_name} 缺少性格特质"
        assert card.casting_guide.actor_type, f"{card.role_name} 缺少选角指引"
    print(f"  ✅ 角色蒸馏验证通过：{len(role_cards)} 个角色")

    # 保存
    RoleDistiller.save_role_cards(role_cards, os.path.join(base, "output", "test_roles.json"))

    # ========== Step 2: 演员画像 ==========
    print("\n" + "=" * 60)
    print("  Step 2: 演员画像")
    print("=" * 60)

    actors_path = os.path.join(base, "examples", "sample_actors.txt")
    with open(actors_path, "r", encoding="utf-8") as f:
        actors_text = f.read()

    import re
    actor_blocks = re.split(r'\n---\s*\n', actors_text.strip())

    profiler = ActorProfiler(llm_client=llm)
    actor_profiles = []

    for block in actor_blocks:
        name_match = re.search(r'【演员[^】]*[:：]\s*([^】]+)】', block)
        actor_name = name_match.group(1).strip() if name_match else "未命名演员"

        profile = profiler.profile_from_text(
            actor_material=block,
            actor_name=actor_name,
        )
        if profile:
            actor_profiles.append(profile)

    assert len(actor_profiles) > 0, "演员画像失败：未生成任何画像"
    for p in actor_profiles:
        assert p.actor_name, "演员名为空"
        assert p.temperament.primary_type, f"{p.actor_name} 缺少气质类型"
        assert p.acting_style.potential, f"{p.actor_name} 缺少潜力评估"
    print(f"  ✅ 演员画像验证通过：{len(actor_profiles)} 位演员")

    # 保存
    ActorProfiler.save_profiles(actor_profiles, os.path.join(base, "output", "test_actors.json"))

    # ========== Step 3: 智能匹配 ==========
    print("\n" + "=" * 60)
    print("  Step 3: 智能匹配")
    print("=" * 60)

    engine = MatchingEngine(llm_client=llm)
    report = engine.match_all(role_cards, actor_profiles)

    expected_matches = len(role_cards) * len(actor_profiles)
    assert len(report.results) == expected_matches, \
        f"匹配结果数量不符：期望 {expected_matches}，实际 {len(report.results)}"

    for r in report.results:
        assert 0 <= r.overall_score <= 100, f"匹配度超出范围：{r.overall_score}"
        assert r.match_level, "匹配等级为空"
        assert r.summary, "综合评价为空"
        assert len(r.dimension_scores) > 0, f"{r.role_name}×{r.actor_name} 缺少分维度评分"
    print(f"  ✅ 智能匹配验证通过：{len(report.results)} 个匹配结果")

    # 推荐汇总
    assert len(report.recommendations) == len(role_cards), "推荐数量与角色数不符"
    print(f"  ✅ 推荐汇总验证通过：{len(report.recommendations)} 个角色推荐")

    # 保存报告
    MatchingEngine.save_report(report, os.path.join(base, "output", "test_report.json"))

    # ========== Step 4: 报告内容检查 ==========
    print("\n" + "=" * 60)
    print("  Step 4: 报告内容检查")
    print("=" * 60)

    for role_name in report.recommendations:
        best = report.get_best_actor_for_role(role_name)
        assert best is not None, f"角色 {role_name} 没有最佳匹配"
        print(f"  {role_name} → {best.actor_name} ({best.overall_score:.0f}分, {best.match_level})")

    # 检查演员适合的角色
    for actor in actor_profiles:
        roles = report.get_roles_for_actor(actor.actor_name)
        assert len(roles) > 0, f"演员 {actor.actor_name} 没有匹配的角色"
        print(f"  {actor.actor_name} 最适合：{roles[0].role_name} ({roles[0].overall_score:.0f}分)")

    print(f"\n  ✅ 报告内容检查通过")

    # ========== 最终总结 ==========
    print("\n" + "=" * 60)
    print("  🎉 端到端验证全部通过！")
    print("=" * 60)
    print(f"  角色蒸馏：{len(role_cards)} 个角色卡")
    print(f"  演员画像：{len(actor_profiles)} 位演员画像")
    print(f"  智能匹配：{len(report.results)} 个匹配结果")
    print(f"  选角报告：已生成并保存")
    print(f"  模式：{'Mock 演示' if llm.is_mock_mode else '真实 AI'}")
    print("=" * 60)


if __name__ == "__main__":
    main()
