#!/usr/bin/env python3
"""
CastingNuwa · 选角女娲 — Web 应用（v0.5 观察记录体系）

核心理念：从"上传材料 → AI 打分排名"，改为"引导学生剧团完成一轮有依据、可复核的选角"。
1. 角色蒸馏：剧本 → 角色卡（含可观察表演要求）
2. 演员观察：试镜材料 → 观察记录（发生了什么→可能意味着什么→依据是否充分→下一轮怎么验证）
3. 候选方案：角色要求 × 观察证据 → 候选方案分类 + 证据比较 + 待验证项
4. 制作团队：剧本 → 后台岗位需求

运行方式：
    pip install gradio openai
    python app.py
"""

import os
import sys
import json
import re

# 修复 OpenMP 运行时冲突（faster-whisper/ctranslate2 与 numpy/opencv 共存时）
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

import gradio as gr

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.role_distiller import RoleDistiller
from src.actor_profiler import ActorProfiler
from src.matching_engine import MatchingEngine
from src.llm_client import LLMClient
from src.models import RoleCard, CrewAnalysisResult
from src.actor_models import ActorProfile
from src.crew_analyzer import CrewAnalyzer


class AppState:
    """应用状态管理"""
    def __init__(self):
        self.llm_client = LLMClient()
        self.role_distiller = RoleDistiller(llm_client=self.llm_client)
        self.actor_profiler = ActorProfiler(llm_client=self.llm_client)
        self.matching_engine = MatchingEngine(llm_client=self.llm_client)
        self.crew_analyzer = CrewAnalyzer(llm_client=self.llm_client)

        self.role_cards = []
        self.actor_profiles = []
        self.casting_report = None
        self.crew_analysis = None

    def is_mock(self):
        return self.llm_client.is_mock_mode


state = AppState()


STATUS_BADGE = {
    "complete": "🟢 **分析完整**",
    "partial": "🟡 **分析部分完成**（部分模态处理失败，结论需补充验证）",
    "failed": "🔴 **分析失败**（未生成有效观察记录，请重试）",
    "demo": "⚪ **演示数据**（未配置真实 AI，不能作为选角依据）",
}

CATEGORY_BADGE = {
    "priority_audition": "🟢【值得优先试演】",
    "needs_more_audition": "🟡【需要补充试镜】",
    "explicit_limit": "🔴【存在明确限制】",
}


def load_example_script():
    path = os.path.join(os.path.dirname(__file__), "examples", "sample_script.txt")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    return ""


def load_example_actors():
    path = os.path.join(os.path.dirname(__file__), "examples", "sample_actors.txt")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    return ""


def format_role_card_markdown(card: RoleCard) -> str:
    """将角色卡格式化为 Markdown"""
    lines = [
        f"## 🎭 {card.role_name}",
        f"",
        f"**身份**：{card.profile.identity or '未提及'}",
        f"**年龄/性别**：{card.profile.age_gender or '未提及'}",
        f"",
        f"### 性格特质",
    ]
    for t in card.personality:
        lines.append(f"- **{t.trait}**：{t.evidence}")
        if t.nuance:
            lines.append(f"  - 细微差别：{t.nuance}")

    lines.extend([
        f"",
        f"### 核心动机",
        f"- **表层欲望（Want）**：{card.motivation.want}",
        f"- **深层需求（Need）**：{card.motivation.need}",
        f"- **核心恐惧**：{card.motivation.fear}",
        f"",
        f"### 语言 DNA",
        f"- 用词：{card.linguistic_dna.vocabulary}",
        f"- 句式：{card.linguistic_dna.sentence_style}",
        f"- 语气：{card.linguistic_dna.tone}",
        f"",
        f"### 情感弧线",
        f"- 开场：{card.emotional_arc.opening_state}",
        f"- 类型：{card.emotional_arc.arc_type}",
        f"- 结尾：{card.emotional_arc.ending_state}",
        f"",
        f"### 🎬 选角指引",
        f"- **适合演员类型**：{card.casting_guide.actor_type}",
        f"- **核心能力要求**：",
    ])
    for req in card.casting_guide.core_requirements:
        lines.append(f"  - {req}")
    lines.extend([
        f"- **试镜重点**：{card.casting_guide.audition_focus}",
        f"- **选角风险**：{card.casting_guide.risks}",
    ])

    observable = card.casting_guide.observable_requirements
    if observable:
        lines.extend([
            f"",
            f"### 🔍 可观察表演要求（试镜对照用）",
            f"> 这些是演员在试镜中**可以被看到/听到**的具体行为，不是性格标签。",
            f"> 例如「角色内向」应转化为「通过停顿、回避目光和有限动作让观众理解角色」。",
            f"",
        ])
        for i, req in enumerate(observable, 1):
            must = "🔴 必须满足" if req.must_have else "⚪ 可排练改善"
            signals = "、".join(req.observable_signals) if req.observable_signals else "见描述"
            lines.append(f"**{i}. {req.requirement}** （{must}）")
            lines.append(f"- 观察信号：{signals}")
            if req.source_trait:
                lines.append(f"- 对应角色特征：{req.source_trait}")
            if req.audition_check:
                lines.append(f"- 试镜检查：{req.audition_check}")
            lines.append("")

    return "\n".join(lines)


def format_actor_profile_markdown(profile: ActorProfile) -> str:
    """将演员观察记录格式化为 Markdown（v0.5：观察记录优先，评分弱化）"""
    status = profile.analysis_status or "complete"
    lines = [
        f"## 🎬 {profile.actor_name}",
        f"",
        STATUS_BADGE.get(status, ""),
        f"",
    ]

    if profile.analysis_warnings:
        lines.append("**⚠️ 分析说明**")
        for w in profile.analysis_warnings:
            lines.append(f"- {w}")
        lines.append("")

    if status == "failed":
        lines.append("本次分析未生成有效观察记录，请检查材料或重新分析。")
        return "\n".join(lines)

    lines.extend([
        f"**年龄/性别**：{profile.basic_info.age_gender or '未提供'}",
        f"**表演经验**：{profile.basic_info.experience or '未提供'}",
        f"",
    ])

    # 核心：观察记录
    if profile.observations:
        lines.append("### 🔍 试镜观察记录")
        lines.append("> 结构：发生了什么 → 可能意味着什么（保留其他解释）→ 依据类型 → 下一轮怎么验证")
        lines.append("")
        for i, obs in enumerate(profile.observations, 1):
            ts = f"**[{obs.timestamp}]** " if obs.timestamp else f"**观察 {i}** "
            lines.append(f"{ts}（来源：{obs.source or '未标注'}）")
            lines.append(f"- 观察到：{obs.observed_behavior}")
            if obs.possible_interpretation:
                lines.append(f"- 可能意味着：{obs.possible_interpretation}")
            if obs.alternative_interpretations:
                lines.append(f"- 其他可能解释：{'；'.join(obs.alternative_interpretations)}")
            lines.append(
                f"- 依据类型：{obs.evidence_type or '未标注'} ｜ 置信度：{obs.confidence or '无法判断'}"
            )
            if obs.verification_suggestion:
                lines.append(f"- 🔁 验证建议：{obs.verification_suggestion}")
            if obs.related_requirement:
                lines.append(f"- 对应角色要求：{obs.related_requirement}")
            lines.append("")

    # 待验证项
    if profile.verification_items:
        lines.append("### ❓ 待验证项（材料不足，不硬给中分）")
        lines.append("")
        for vi in profile.verification_items:
            pri = {"高": "🔴", "中": "🟡", "低": "⚪"}.get(vi.priority, "⚪")
            lines.append(f"- {pri} **{vi.item}**（优先级：{vi.priority or '未标'}）")
            if vi.why_needed:
                lines.append(f"  - 为何需要：{vi.why_needed}")
            if vi.current_evidence:
                lines.append(f"  - 现有证据：{vi.current_evidence}")
            if vi.suggested_task:
                lines.append(f"  - 补充试镜任务：{vi.suggested_task}")
        lines.append("")

    # 指导后复试
    if profile.adjustment_responses:
        lines.append("### 🔁 指导后复试记录")
        lines.append("> 用于区分「第一次碰巧合适」与「能理解并执行指导」")
        lines.append("")
        for adj in profile.adjustment_responses:
            lines.append(f"- **调整指令**：{adj.instruction_given}")
            if adj.observed_change:
                lines.append(f"  - 观察到的变化：{adj.observed_change}")
            if adj.change_quality:
                lines.append(f"  - 调整效果：{adj.change_quality}")
            if adj.interpretation:
                lines.append(f"  - 解读：{adj.interpretation}")
            lines.append(f"  - 置信度：{adj.confidence or '无法判断'}")
        lines.append("")

    # 证据按来源分离
    ev = profile.evidence
    if ev and (ev.self_reports or ev.past_experience or ev.material_gaps):
        lines.append("### 📎 证据来源区分")
        lines.append("> 自我介绍/自述 ≠ 已在表演中展示的能力")
        lines.append("")
        if ev.self_reports:
            lines.append("**演员自述（未经表演验证）**")
            for s in ev.self_reports:
                lines.append(f"- {s}")
            lines.append("")
        if ev.past_experience:
            lines.append("**过往经历**")
            for s in ev.past_experience:
                lines.append(f"- {s}")
            lines.append("")
        if ev.material_gaps:
            lines.append("**材料缺口**")
            for s in ev.material_gaps:
                lines.append(f"- {s}")
            lines.append("")

    # 客观特征（特征强度，非演技）
    lines.append("### 📊 特征强度参考（不是演技评分）")
    lines.append("")
    lines.append("> ⚠️ 以下是表演**外放程度/风格**，不是演技好坏；克制的表演可能非常出色。")
    lines.append("")
    trait_names = {
        "extraversion": "外向性", "emotional_intensity": "情感张力",
        "rationality": "理性度", "dominance": "强势度", "credibility": "可信度",
    }
    for key, name in trait_names.items():
        trait = profile.quantitative_traits.get(key)
        if trait and trait.score is not None:
            lines.append(
                f"- {name}：{trait.score}/10（{trait.confidence}，{trait.evidence_count}条证据）"
            )
        else:
            lines.append(f"- {name}：无法判断（证据不足）")
    lines.append("")

    if profile.vocal_traits.pitch or profile.vocal_traits.timbre:
        lines.append("<details><summary>声线 / 面部 / 肢体客观描述</summary>")
        lines.append("")
        lines.append(f"- 声线：音高 {profile.vocal_traits.pitch or '未分析'}；音色 {profile.vocal_traits.timbre or '未分析'}；语速 {profile.vocal_traits.pace or '未分析'}")
        lines.append(f"- 面部：{profile.facial_expressiveness.expression_range or '未分析'}；眼神 {profile.facial_expressiveness.eye_contact or '未分析'}")
        lines.append(f"- 肢体：{profile.physical_expressiveness.gesture_richness or '未分析'}；姿态 {profile.physical_expressiveness.posture_naturalness or '未分析'}")
        if profile.temperament.primary_type:
            lines.append(f"- 气质：{profile.temperament.primary_type}")
        if profile.acting_style.development_suggestions:
            lines.append("- 发展建议：")
            for s in profile.acting_style.development_suggestions:
                lines.append(f"  - {s}")
        lines.append("")
        lines.append("</details>")
        lines.append("")

    return "\n".join(lines)


def format_proposal_markdown(proposal, role_name: str = "") -> str:
    """将单个候选方案格式化为 Markdown（v0.5）"""
    badge = CATEGORY_BADGE.get(proposal.category, f"【{proposal.category}】")
    title = f"### {badge} {proposal.actor_name}"
    if role_name:
        title = f"### {badge} {proposal.actor_name} × 角色「{role_name}」"

    lines = [title, ""]

    if proposal.evidence_comparisons:
        lines.append("**证据逐条对照**")
        lines.append("")
        lines.append("| 角色可观察要求 | 硬性 | 证据状态 | 演员观察证据 / 说明 |")
        lines.append("|----------------|------|----------|---------------------|")
        icon_map = {
            "supported": "✅支持", "partial": "🟡部分",
            "missing": "⚪缺失", "contradicted": "⚠️相反",
        }
        for c in proposal.evidence_comparisons:
            must = "🔴" if c.must_have else "⚪"
            icon = icon_map.get(c.evidence_status, c.evidence_status)
            evidence = "；".join(c.actor_evidence) if c.actor_evidence else (c.notes or "")
            evidence = evidence.replace("|", "/").replace("\n", " ")
            req = c.requirement.replace("|", "/")
            lines.append(f"| {req} | {must} | {icon} | {evidence} |")
        lines.append("")

    if proposal.supported_requirements:
        lines.append("**✅ 已有证据支持的要求**")
        for r in proposal.supported_requirements:
            lines.append(f"- {r}")
        lines.append("")

    if proposal.missing_evidence:
        lines.append("**❓ 还缺什么证据**")
        for m in proposal.missing_evidence:
            lines.append(f"- {m}")
        lines.append("")

    if proposal.explicit_limits:
        lines.append("**🔴 明确限制**")
        for item in proposal.explicit_limits:
            lines.append(f"- {item}")
        lines.append("")

    if proposal.stability_note:
        lines.append(f"- **当前稳定性**：{proposal.stability_note}")
    if proposal.adjustment_note:
        lines.append(f"- **指导后复试**：{proposal.adjustment_note}")
    if proposal.tradeoffs:
        lines.append(f"- **方案取舍**：{proposal.tradeoffs}")

    if proposal.next_steps:
        lines.append("")
        lines.append("**➡️ 下一步**")
        for s in proposal.next_steps:
            lines.append(f"- {s}")

    lines.append("")
    lines.append(
        f"<sub>数值特征参考分：{proposal.reference_score:.0f}/100"
        f"（仅反映特征强度相似度，**不是演技评分，也不是匹配结论**）</sub>"
    )

    return "\n".join(lines)


def format_crew_analysis_markdown(analysis: CrewAnalysisResult) -> str:
    """将制作团队需求分析结果格式化为 Markdown"""
    if not analysis or not analysis.requirements:
        return "### 暂无分析结果\n\n请输入剧本后点击分析按钮。"

    lines = [
        f"## 🎬 制作团队需求分析",
        f"",
        f"**剧本**：{analysis.script_title or '未识别'}",
        f"**场景数**：{analysis.total_scenes} | **角色数**：{analysis.total_characters}",
        f"**制作规模**：{analysis.production_scale or '未评估'}",
        f"",
    ]

    needed = [r for r in analysis.requirements.values() if r.needed]
    not_needed = [r for r in analysis.requirements.values() if not r.needed]

    if needed:
        lines.append("### ✅ 需要的岗位")
        lines.append("")
        lines.append("| 岗位 | 人数 | 复杂度 | 核心技能 |")
        lines.append("|------|------|--------|----------|")
        for r in needed:
            skills = "、".join(r.skill_requirements[:2]) if r.skill_requirements else "-"
            lines.append(f"| {r.role_name} | {r.headcount}人 | {r.complexity}/10 | {skills} |")
        lines.append("")

    if not_needed:
        lines.append("### ➖ 不需要的岗位")
        lines.append("")
        lines.append(f"{', '.join(r.role_name for r in not_needed)}")
        lines.append("")

    lines.append("### 📋 岗位详情")
    lines.append("")
    for req in analysis.requirements.values():
        status = "✅ 需要" if req.needed else "➖ 不需要"
        lines.append(f"#### {req.role_name}（{status}）")
        lines.append("")
        if req.needed:
            lines.append(f"- **建议人数**：{req.headcount}人")
            lines.append(f"- **复杂度**：{req.complexity}/10")
            if req.skill_requirements:
                lines.append(f"- **技能要求**：{', '.join(req.skill_requirements)}")
            if req.special_needs:
                lines.append(f"- **特殊需求**：{req.special_needs}")
            if req.evidence:
                lines.append("- **剧本依据**：")
                for ev in req.evidence[:3]:
                    lines.append(f"  - {ev}")
                if len(req.evidence) > 3:
                    lines.append(f"  - ... 等共{len(req.evidence)}条")
            if req.notes:
                lines.append(f"- **备注**：{req.notes}")
        else:
            if req.notes:
                lines.append(f"- {req.notes}")
            elif req.evidence:
                lines.append(f"- 依据：{req.evidence[0]}")
        lines.append("")

    if analysis.overall_summary:
        lines.append("### 💡 总体建议")
        lines.append("")
        lines.append(f"> {analysis.overall_summary}")
        lines.append("")

    return "\n".join(lines)


# ============================================================
# 标签页 1：角色蒸馏
# ============================================================

def distill_roles(script_text):
    """执行角色蒸馏，返回 (markdown, json, 匹配页角色下拉, 观察页角色下拉)"""
    if not script_text or not script_text.strip():
        empty = gr.update(choices=[], value=None)
        return "⚠️ 请输入剧本内容", "", empty, empty

    candidates = RoleDistiller.extract_characters_from_script(script_text)
    candidate_info = f"检测到候选角色：{', '.join(candidates)}" if candidates else "未检测到明确角色名"

    role_cards = state.role_distiller.distill_all(script_text)
    state.role_cards = role_cards

    if not role_cards:
        empty = gr.update(choices=[], value=None)
        return f"❌ 角色蒸馏失败\n\n{candidate_info}", "", empty, empty

    md_parts = [f"### 蒸馏完成：共 {len(role_cards)} 个角色\n"]
    md_parts.append(
        "> 💡 下一步：请负责人**核对并修改**角色要求（尤其是可观察表演要求），"
        "确认后再到「② 演员观察」页对照角色记录试镜表现。"
    )
    md_parts.append("")
    for card in role_cards:
        md_parts.append(format_role_card_markdown(card))
        md_parts.append("\n---\n")

    json_output = json.dumps(
        {"roles": [c.to_dict() for c in role_cards]},
        indent=2, ensure_ascii=False
    )

    role_names = [c.role_name for c in role_cards]
    dropdown_update = gr.update(choices=role_names, value=role_names[0] if role_names else None)
    return "\n".join(md_parts), json_output, dropdown_update, dropdown_update


# ============================================================
# 标签页 2：演员观察记录
# ============================================================

def build_role_requirements_text(role_name: str) -> str:
    """从角色卡提取可观察表演要求，拼成给演员分析器的对照文本"""
    if not role_name:
        return "（本次未指定对照角色，请基于材料生成通用观察记录和待验证项）"
    role = next((r for r in state.role_cards if r.role_name == role_name), None)
    if not role or not role.casting_guide.observable_requirements:
        return f"（角色「{role_name}」缺少可观察表演要求，请生成通用观察记录）"

    lines = [f"本次试镜对照角色「{role_name}」，请重点观察以下可观察表演要求："]
    for i, req in enumerate(role.casting_guide.observable_requirements, 1):
        must = "必须满足" if req.must_have else "可排练改善"
        signals = "、".join(req.observable_signals) if req.observable_signals else ""
        lines.append(f"{i}. {req.requirement}（{must}；观察信号：{signals}）")
    return "\n".join(lines)


def profile_actors(actor_text, target_role_name):
    """执行演员观察记录（文本模式）"""
    if not actor_text or not actor_text.strip():
        return "⚠️ 请输入演员材料", ""

    role_requirements = build_role_requirements_text(target_role_name)
    actor_blocks = re.split(r'\n---\s*\n', actor_text.strip())

    profiles = []
    for block in actor_blocks:
        name_match = re.search(r'【演员[^】]*[:：]\s*([^】]+)】', block)
        actor_name = name_match.group(1).strip() if name_match else "未命名演员"

        profile = state.actor_profiler.profile_from_text(
            actor_material=block,
            actor_name=actor_name,
            role_requirements=role_requirements,
        )
        if profile:
            profiles.append(profile)

    state.actor_profiles = profiles

    if not profiles:
        return "❌ 演员观察记录生成失败", ""

    md_parts = [f"### 观察记录完成：共 {len(profiles)} 位演员\n"]
    for p in profiles:
        md_parts.append(format_actor_profile_markdown(p))
        md_parts.append("\n---\n")

    json_output = json.dumps(
        {"actors": [p.to_dict() for p in profiles]},
        indent=2, ensure_ascii=False
    )

    return "\n".join(md_parts), json_output


def profile_from_video_file(video_path, actor_name, text_material):
    """从视频文件生成演员观察记录（三模态）"""
    if not video_path:
        return "⚠️ 请先上传视频文件", ""

    print(f"\n[Web] 从视频生成观察记录: {video_path}")
    try:
        profile = state.actor_profiler.profile_from_video(
            video_path=video_path,
            actor_name=actor_name or "视频演员",
            text_material=text_material or "",
        )
        if profile is None:
            return "❌ 视频分析失败", ""

        state.actor_profiles.append(profile)
        return format_actor_profile_markdown(profile), profile.to_json()
    except Exception as e:
        import traceback
        error_msg = f"❌ 视频处理出错：{str(e)}\n\n{traceback.format_exc()}"
        error_json = json.dumps(
            {"success": False, "error": str(e), "type": type(e).__name__},
            indent=2, ensure_ascii=False,
        )
        return error_msg, error_json


def profile_from_audio_file(audio_path, actor_name, text_material):
    """从音频文件生成演员观察记录（双模态）"""
    if not audio_path:
        return "⚠️ 请先上传音频文件", ""

    print(f"\n[Web] 从音频生成观察记录: {audio_path}")
    try:
        profile = state.actor_profiler.profile_from_audio(
            audio_path=audio_path,
            actor_name=actor_name or "音频演员",
            text_material=text_material or "",
        )
        if profile is None:
            return "❌ 音频分析失败", ""

        state.actor_profiles.append(profile)
        return format_actor_profile_markdown(profile), profile.to_json()
    except Exception as e:
        import traceback
        return f"❌ 音频处理出错：{str(e)}\n\n{traceback.format_exc()}", ""


# ============================================================
# 标签页 3：候选方案
# ============================================================

def match_single(role_name, actor_name):
    """对照单个角色和演员，生成候选方案"""
    if not role_name or not actor_name:
        return "⚠️ 请先在前面的标签页生成角色卡和演员观察记录"

    role = next((r for r in state.role_cards if r.role_name == role_name), None)
    actor = next((a for a in state.actor_profiles if a.actor_name == actor_name), None)

    if not role or not actor:
        return "❌ 未找到对应的角色卡或演员观察记录"

    proposal = state.matching_engine.match_one(role, actor)
    if not proposal:
        return "❌ 候选方案生成失败"

    return format_proposal_markdown(proposal, role_name=role_name)


def run_full_matching():
    """执行全量候选方案整理，返回 (markdown, json)"""
    if not state.role_cards or not state.actor_profiles:
        return "⚠️ 请先在前面的标签页生成角色卡和演员观察记录", ""

    report = state.matching_engine.match_all(state.role_cards, state.actor_profiles)
    state.casting_report = report

    lines = [
        f"## 📋 选角候选方案报告",
        f"",
        f"**角色数**：{report.role_count} | **演员数**：{report.actor_count}",
        f"",
        f"> ⚠️ 本报告**不是排名**，而是按角色的可观察要求逐条核对证据，",
        f"> 帮助导演决定谁优先试演、谁需要补充试镜。最终判断权在导演。",
        f"",
        f"### 🗺️ 候选概览",
        f"",
        f"| 角色 | 优先试演 | 需补充试镜 | 明确限制 |",
        f"|------|----------|-----------|----------|",
    ]
    for role_result in report.results:
        priority = [p.actor_name for p in role_result.proposals if p.category == "priority_audition"]
        more = [p.actor_name for p in role_result.proposals if p.category == "needs_more_audition"]
        limit = [p.actor_name for p in role_result.proposals if p.category == "explicit_limit"]
        lines.append(
            f"| {role_result.role_name} | "
            f"{', '.join(priority) or '—'} | "
            f"{', '.join(more) or '—'} | "
            f"{', '.join(limit) or '—'} |"
        )
    lines.append("")

    lines.append("### 📝 分角色候选方案")
    lines.append("")
    for role_result in report.results:
        lines.append(f"## 🎭 角色：{role_result.role_name}")
        lines.append("")
        for proposal in role_result.proposals:
            lines.append(format_proposal_markdown(proposal, role_name=role_result.role_name))
            lines.append("")

        if role_result.chemistry_checks:
            lines.append("**🧪 化学反应验证（单人试镜无法判断，需安排对手戏）**")
            for chk in role_result.chemistry_checks:
                lines.append(f"- {chk}")
            lines.append("")
        lines.append("---")
        lines.append("")

    if report.global_notes:
        lines.append("### ⚠️ 全局说明")
        for note in report.global_notes:
            lines.append(f"- {note}")
        lines.append("")

    return "\n".join(lines), report.to_json()


# ============================================================
# 标签页 4：制作团队需求分析
# ============================================================

def analyze_crew(script_text):
    """执行制作团队需求分析"""
    if not script_text or not script_text.strip():
        return "⚠️ 请输入剧本内容", ""

    try:
        analysis = state.crew_analyzer.analyze(script_text)
        state.crew_analysis = analysis
        return format_crew_analysis_markdown(analysis), analysis.to_json()
    except Exception as e:
        return f"❌ 分析失败：{str(e)}", ""


# ============================================================
# Gradio 界面构建
# ============================================================

def build_ui():
    """构建 Gradio 界面"""

    with gr.Blocks(title="CastingNuwa · 选角女娲") as demo:

        gr.Markdown("# 🎭 CastingNuwa · 选角女娲", elem_classes="main-title")
        gr.Markdown("### 引导学生剧团完成一轮有依据、可复核的选角", elem_classes="subtitle")
        gr.Markdown(
            "女娲造人，我们造角色卡。系统不替导演打分下结论，"
            "而是帮你**把角色要求变成可观察行为、把试镜表现整理成证据、把候选方案讲清依据**。"
        )

        if state.is_mock():
            gr.Markdown(
                "⚠️ **当前为演示模式**：未配置 LLM API Key，输出为示例数据（页面会明确标注）。"
                "配置 `LLM_API_KEY` 环境变量后可使用真实 AI 分析。详见 `.env.example`。",
                elem_classes="mock-banner",
            )

        with gr.Tabs():

            # ===== 标签页 1：角色蒸馏 =====
            with gr.Tab("① 角色蒸馏"):
                gr.Markdown("### 第 1 步：输入剧本，蒸馏角色卡与**可观察表演要求**")
                with gr.Row():
                    with gr.Column(scale=1):
                        script_input = gr.Textbox(
                            label="剧本内容",
                            placeholder="在此粘贴剧本，或点击下方按钮加载示例剧本...",
                            lines=20, value=load_example_script(),
                        )
                        with gr.Row():
                            load_example_btn = gr.Button("📄 加载示例剧本", variant="secondary")
                            clear_btn = gr.Button("🗑️ 清空", variant="secondary")
                            distill_btn = gr.Button("🎭 开始角色蒸馏", variant="primary", size="lg")
                    with gr.Column(scale=1):
                        role_output = gr.Markdown(label="角色卡结果")
                        role_json = gr.Code(label="JSON 输出", language="json", visible=True)

                load_example_btn.click(fn=load_example_script, outputs=script_input)
                clear_btn.click(fn=lambda: "", outputs=script_input)

            # ===== 标签页 2：演员观察 =====
            with gr.Tab("② 演员观察"):
                gr.Markdown("### 第 2 步：记录试镜表现，输出**观察记录**而非演技打分")
                gr.Markdown(
                    "> 每条观察：发生了什么（时间戳）→ 可能意味着什么（保留其他解释）"
                    "→ 依据类型 → 下一轮怎么验证。材料不足生成**待验证项**，不硬给中等分。"
                )
                with gr.Tabs():
                    with gr.Tab("📝 文本模式"):
                        with gr.Row():
                            with gr.Column(scale=1):
                                target_role_dropdown = gr.Dropdown(
                                    label="对照角色（可选，建议先在第①步生成角色卡）",
                                    choices=[], interactive=True,
                                )
                                actor_input = gr.Textbox(
                                    label="演员试镜材料",
                                    placeholder="粘贴演员自我介绍和试镜片段转写...\n\n多位演员用 --- 分隔。",
                                    lines=16, value=load_example_actors(),
                                )
                                with gr.Row():
                                    load_actor_btn = gr.Button("📄 加载示例", variant="secondary")
                                    clear_actor_btn = gr.Button("🗑️ 清空", variant="secondary")
                                    profile_btn = gr.Button("🎬 生成观察记录", variant="primary", size="lg")
                            with gr.Column(scale=1):
                                actor_output = gr.Markdown(label="观察记录结果")
                                actor_json = gr.Code(label="JSON 输出", language="json")

                        load_actor_btn.click(fn=load_example_actors, outputs=actor_input)
                        clear_actor_btn.click(fn=lambda: "", outputs=actor_input)
                        profile_btn.click(
                            fn=profile_actors,
                            inputs=[actor_input, target_role_dropdown],
                            outputs=[actor_output, actor_json],
                        )

                    with gr.Tab("🎥 视频模式（三模态）"):
                        gr.Markdown(
                            "上传试镜视频，提取音频（转写+声学）与视觉（面部/肢体）线索，整理成观察记录。"
                            "**声音/动作变化只是线索，不直接等同于演得好。**"
                        )
                        with gr.Row():
                            with gr.Column(scale=1):
                                video_actor_name = gr.Textbox(label="演员姓名（可选）")
                                video_upload = gr.Video(label="上传试镜视频", sources=["upload"])
                                video_extra_text = gr.Textbox(
                                    label="额外文本材料（可选，如自我介绍）", lines=4,
                                )
                                video_profile_btn = gr.Button(
                                    "🎬 从视频生成观察记录（三模态）", variant="primary", size="lg",
                                )
                                gr.Markdown(
                                    "**客观线索：**\n"
                                    "- 🎵 音频：转写 + 音高/音色/语速/停顿\n"
                                    "- 👤 视觉：面部关键点 + 姿态（环境不支持会标注降级）\n"
                                    "- 🧠 整理为带时间戳的观察记录与待验证项"
                                )
                            with gr.Column(scale=1):
                                video_output = gr.Markdown(label="视频观察结果")
                                video_json = gr.Code(label="JSON 输出", language="json")

                        video_profile_btn.click(
                            fn=profile_from_video_file,
                            inputs=[video_upload, video_actor_name, video_extra_text],
                            outputs=[video_output, video_json],
                        )

                    with gr.Tab("🎵 音频模式（双模态）"):
                        gr.Markdown("上传试镜音频，进行转写 + 声学特征分析，整理为观察记录。")
                        with gr.Row():
                            with gr.Column(scale=1):
                                audio_actor_name = gr.Textbox(label="演员姓名（可选）")
                                audio_upload = gr.Audio(
                                    label="上传试镜音频", sources=["upload"], type="filepath",
                                )
                                audio_extra_text = gr.Textbox(
                                    label="额外文本材料（可选，如自我介绍）", lines=4,
                                )
                                audio_profile_btn = gr.Button(
                                    "🎬 从音频生成观察记录（双模态）", variant="primary", size="lg",
                                )
                            with gr.Column(scale=1):
                                audio_output = gr.Markdown(label="音频观察结果")
                                audio_json = gr.Code(label="JSON 输出", language="json")

                        audio_profile_btn.click(
                            fn=profile_from_audio_file,
                            inputs=[audio_upload, audio_actor_name, audio_extra_text],
                            outputs=[audio_output, audio_json],
                        )

            # ===== 标签页 3：候选方案 =====
            with gr.Tab("③ 候选方案"):
                gr.Markdown("### 第 3 步：按角色的可观察要求逐条核对证据，给出候选方案")
                gr.Markdown(
                    "> 🟢 值得优先试演 / 🟡 需要补充试镜 / 🔴 存在明确限制。"
                    "单人试镜无法判断化学反应，会建议安排对手戏。"
                )
                with gr.Row():
                    with gr.Column(scale=1):
                        gr.Markdown("**请先在第①②步生成角色卡和演员观察记录**")
                        role_dropdown = gr.Dropdown(label="选择角色", choices=[], interactive=True)
                        actor_dropdown = gr.Dropdown(label="选择演员（单个对照）", choices=[], interactive=True)
                        refresh_btn = gr.Button("🔄 刷新列表", variant="secondary")
                        match_btn = gr.Button("🎯 生成单个候选方案", variant="primary", size="lg")
                        gr.Markdown("---")
                        full_match_btn = gr.Button(
                            "📋 整理全量候选方案（所有角色×所有演员）", variant="primary"
                        )
                    with gr.Column(scale=2):
                        match_output = gr.Markdown(label="候选方案结果")
                        match_json = gr.Code(label="JSON 输出", language="json", visible=False)

                distill_btn.click(
                    fn=distill_roles,
                    inputs=script_input,
                    outputs=[role_output, role_json, role_dropdown, target_role_dropdown],
                )

                def refresh_all_dropdowns():
                    role_names = [r.role_name for r in state.role_cards]
                    actor_names = [a.actor_name for a in state.actor_profiles]
                    role_upd = gr.update(choices=role_names, value=role_names[0] if role_names else None)
                    actor_upd = gr.update(choices=actor_names, value=actor_names[0] if actor_names else None)
                    return role_upd, actor_upd, role_upd

                refresh_btn.click(
                    fn=refresh_all_dropdowns,
                    outputs=[role_dropdown, actor_dropdown, target_role_dropdown],
                )
                match_btn.click(fn=match_single, inputs=[role_dropdown, actor_dropdown], outputs=match_output)
                full_match_btn.click(fn=run_full_matching, outputs=[match_output, match_json])

            # ===== 标签页 4：制作团队 =====
            with gr.Tab("④ 制作团队分析"):
                gr.Markdown("### 输入剧本，分析所需的后台岗位与人员配置")
                gr.Markdown("支持分析：灯光师、音效师、舞美设计、服装师、道具师、化妆师")
                with gr.Row():
                    with gr.Column(scale=1):
                        crew_script_input = gr.Textbox(
                            label="剧本内容",
                            placeholder="粘贴剧本，包含舞台指示、场景描述、灯光/音效提示等...",
                            lines=18,
                        )
                        with gr.Row():
                            crew_load_example_btn = gr.Button("📄 加载示例剧本", variant="secondary")
                            crew_analyze_btn = gr.Button("🔍 分析制作团队需求", variant="primary", size="lg")
                        gr.Markdown("---")
                        gr.Markdown(
                            "**分析维度：**\n"
                            "- 灯光师：灯光提示、场景切换、特殊光效\n"
                            "- 音效师：音效提示、背景音乐、现场播放\n"
                            "- 舞美设计：场景数量、换景难度、舞台装置\n"
                            "- 服装师：服装描述、换装次数、特殊服装\n"
                            "- 道具师：手持道具、场景道具、特殊道具\n"
                            "- 化妆师：特殊化妆、妆面变化"
                        )
                    with gr.Column(scale=2):
                        crew_output = gr.Markdown(label="分析结果")
                        with gr.Accordion("📋 JSON 原始数据", open=False):
                            crew_json_output = gr.Code(label="JSON", language="json")

                crew_load_example_btn.click(fn=load_example_script, outputs=crew_script_input)
                crew_analyze_btn.click(
                    fn=analyze_crew, inputs=crew_script_input,
                    outputs=[crew_output, crew_json_output],
                )

            # ===== 标签页 5：关于 =====
            with gr.Tab("ℹ️ 关于"):
                gr.Markdown("""
                ## CastingNuwa · 选角女娲（v0.5 观察记录体系）

                ### 这个工具解决什么问题
                学生剧团选角常依赖导演个人直觉，角色描述与实际配置之间存在信息断层，
                导致初筛效率低、依据难复核。本工具不替导演做决定，而是**把选角过程结构化、可追溯**。

                ### 核心原则：AI 整理观察，而不是鉴定演技
                - **特征强度 ≠ 表演质量 ≠ 角色匹配**：外放程度是风格，不是演技好坏；
                  克制的表演可能非常出色；性格相似也不等于适合出演。
                - **观察记录四要素**：发生了什么（时间戳）→ 可能意味着什么（保留其他解释）
                  → 依据是否充分 → 下一轮怎么验证。
                - **材料不足给待验证项，不硬给中等分**；自述"擅长"不等于"已展示能力"。
                - **指导后复试**：给明确调整指令再演一遍，区分"碰巧合适"与"能执行指导"。

                ### 工作流程
                1. **角色蒸馏**：剧本 → 角色卡，把性格标签转成**可观察表演要求**
                2. **演员观察**：试镜材料 → 观察记录 + 待验证项（文本/音频/视频）
                3. **候选方案**：逐条核对证据 → 优先试演 / 补充试镜 / 明确限制 + 对手戏建议
                4. **人工确认**：导演结合试演与化学反应做最终决定，并保存理由
                5. **制作团队分析**：剧本 → 灯光/音效/舞美/服装/道具/化妆岗位需求

                ### 灵感来源
                灵感来自 GitHub 开源项目 [nuwa-skill](https://github.com/alchaincyf/nuwa-skill)（女娲.skill）：
                女娲蒸馏人物思维方式，本项目蒸馏戏剧角色的"认知操作系统"并服务于可复核选角。

                ### 技术栈
                - LLM：OpenAI 兼容 API（DeepSeek / 智谱 GLM / 豆包 / 通义千问等）
                - 多模态：faster-whisper（语音）、librosa（声学）、MediaPipe / OpenCV（视觉，可降级）
                - Web：Gradio ｜ 数据模型：Python dataclass + JSON
                """)

        gr.Markdown("---")
        gr.Markdown("*CastingNuwa · 选角女娲 v0.5 | 引导有依据、可复核的戏剧选角，AI 整理观察而非替代判断*")

    return demo


if __name__ == "__main__":
    demo = build_ui()
    demo.launch(
        server_name="127.0.0.1",
        server_port=7860,
        share=False,
        inbrowser=True,
        theme=gr.themes.Soft(),
        css="""
        .main-title { text-align: center; margin-bottom: 0; }
        .subtitle { text-align: center; color: #666; margin-top: 0; }
        .mock-banner { background: #fff3cd; padding: 10px; border-radius: 8px; text-align: center; }
        """,
    )
