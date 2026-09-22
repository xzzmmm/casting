"""
CastingNuwa 端到端验证脚本（v0.6 更新）
测试完整工作流：角色蒸馏 → 演员观察 → 候选方案（按角色聚合）→ 人工确认

v0.6 变化：匹配结果不再是“角色 × 演员”逐对评分，而是每个角色一条聚合结果，
内含每位演员的候选分类（优先试演 / 补充试镜 / 明确限制）与证据对照。
"""
import os
import sys
import re

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.role_distiller import RoleDistiller
from src.actor_profiler import ActorProfiler
from src.matching_engine import MatchingEngine
from src.llm_client import LLMClient
from src.models import ProductionSettings

VALID_CATEGORIES = {
    "priority_audition",
    "needs_more_audition",
    "explicit_limit",
}


def main():
    print("=" * 60)
    print("  CastingNuwa 端到端验证（v0.6）")
    print("=" * 60)

    base = os.path.dirname(os.path.abspath(__file__))
    os.makedirs(os.path.join(base, "output"), exist_ok=True)
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

    RoleDistiller.save_role_cards(
        role_cards, os.path.join(base, "output", "test_roles.json")
    )

    # ========== Step 2: 演员观察 ==========
    print("\n" + "=" * 60)
    print("  Step 2: 演员观察")
    print("=" * 60)

    actors_path = os.path.join(base, "examples", "sample_actors.txt")
    with open(actors_path, "r", encoding="utf-8") as f:
        actors_text = f.read()

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

    assert len(actor_profiles) > 0, "演员观察失败：未生成任何记录"
    for p in actor_profiles:
        assert p.actor_name, "演员名为空"
        assert p.temperament.primary_type, f"{p.actor_name} 缺少气质类型"
        assert p.acting_style.potential, f"{p.actor_name} 缺少潜力评估"
    print(f"  ✅ 演员观察验证通过：{len(actor_profiles)} 位演员")

    ActorProfiler.save_profiles(
        actor_profiles, os.path.join(base, "output", "test_actors.json")
    )

    # ========== Step 3: 候选方案（按角色聚合） ==========
    print("\n" + "=" * 60)
    print("  Step 3: 候选方案（按角色聚合）")
    print("=" * 60)

    engine = MatchingEngine(llm_client=llm)
    settings = ProductionSettings(confirmed=True)
    report = engine.match_all(
        role_cards, actor_profiles, production_settings=settings
    )

    # 每个角色一条聚合结果，而不是角色×演员逐对结果
    assert len(report.results) == len(role_cards), (
        f"聚合结果数量应为角色数 {len(role_cards)}，实际 {len(report.results)}"
    )
    assert report.role_count == len(role_cards)
    assert report.actor_count == len(actor_profiles)

    actor_name_set = {a.actor_name for a in actor_profiles}
    for result in report.results:
        assert result.role_name, "存在空角色名的结果"
        assert report.get_result_for_role(result.role_name) is result
        assert len(result.proposals) == len(actor_profiles), (
            f"{result.role_name} 的候选数应为演员数 {len(actor_profiles)}"
        )
        proposal_names = [p.actor_name for p in result.proposals]
        assert len(set(proposal_names)) == len(proposal_names), "同角色候选演员重复"
        for proposal in result.proposals:
            assert proposal.actor_name in actor_name_set, "候选演员不在输入名单中"
            assert proposal.category in VALID_CATEGORIES, (
                f"非法候选类别：{proposal.category}"
            )
            assert 0 <= proposal.reference_score <= 100, "参考分超出 0-100"
    print(f"  ✅ 候选方案验证通过：{len(report.results)} 个角色，"
          f"每角色 {len(actor_profiles)} 位候选")

    MatchingEngine.save_report(
        report, os.path.join(base, "output", "test_report.json")
    )

    # ========== Step 4: 分类概览与人工确认 ==========
    print("\n" + "=" * 60)
    print("  Step 4: 分类概览与人工确认")
    print("=" * 60)

    for result in report.results:
        priority = [p.actor_name for p in result.proposals
                    if p.category == "priority_audition"]
        more = [p.actor_name for p in result.proposals
                if p.category == "needs_more_audition"]
        limit = [p.actor_name for p in result.proposals
                 if p.category == "explicit_limit"]
        print(f"  {result.role_name}：优先 {priority or '—'} | "
              f"补充 {more or '—'} | 限制 {limit or '—'}")
        # 无证据不得给优先：优先候选必须至少带一条 supported 证据
        for proposal in result.proposals:
            if proposal.category == "priority_audition":
                supported = [c for c in proposal.evidence_comparisons
                             if c.evidence_status == "supported"]
                assert supported, f"{result.role_name}×{proposal.actor_name} 无支持证据却给优先"

    # 人工确认：正常确认并记录理由；不在候选中的演员被拒绝
    first = report.results[0]
    chosen = first.proposals[0].actor_name
    assert report.confirm_actor(first.role_name, chosen, "试镜表现贴合可观察要求")
    assert report.get_result_for_role(first.role_name).confirmed_actor_name == chosen
    assert not report.confirm_actor(first.role_name, "不存在的演员", "无效")
    print("  ✅ 人工确认与理由保存验证通过")

    # ========== 最终总结 ==========
    print("\n" + "=" * 60)
    print("  🎉 端到端验证全部通过！")
    print("=" * 60)
    print(f"  角色蒸馏：{len(role_cards)} 个角色卡")
    print(f"  演员观察：{len(actor_profiles)} 位演员记录")
    print(f"  候选方案：{len(report.results)} 个角色的聚合结果")
    print(f"  模式：{'Mock 演示' if llm.is_mock_mode else '真实 AI'}")
    print("=" * 60)


if __name__ == "__main__":
    main()
