#!/usr/bin/env python3
"""
CastingNuwa · 选角女娲 — Web 应用（v0.6 引导式选角流程）

核心理念：从"上传材料 → AI 打分排名"，改为"引导学生剧团完成一轮有依据、可复核的选角"。

流程标签页：
1. 角色蒸馏：剧本 → 角色卡（含可观察表演要求）
2. 选角设定：录入表演风格/必须满足项/可排练项/反串兼角/档期，负责人确认后才进入匹配
3. 试镜任务：角色要求 → 统一试镜材料 + 观察重点 + 调整指令 + 复试任务
4. 演员观察：试镜材料（含指导后复试）→ 观察记录，而非演技打分
5. 候选方案：证据对照 → 候选分类 + 兼角/档期/对手戏检查 + 人工确认并保存理由
6. 制作团队：剧本 → 后台岗位需求

工程要点：
- 会话隔离：每个浏览器会话一个 AppState（gr.State 懒初始化）
- 真实 API 失败明确报错，绝不用演示数据冒充真实结果
- 项目可保存为 JSON、可重新加载；剧本更新后提示下游重算

运行方式：
    pip install gradio openai
    python app.py
"""

import os
import sys
import json
import re
from datetime import datetime

# 修复 OpenMP 运行时冲突（faster-whisper/ctranslate2 与 numpy/opencv 共存时）
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

import gradio as gr

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.role_distiller import RoleDistiller
from src.actor_profiler import ActorProfiler
from src.matching_engine import MatchingEngine
from src.crew_analyzer import CrewAnalyzer
from src.audition_designer import AuditionDesigner
from src.llm_client import LLMClient, LLMServiceError
from src.models import (
    RoleCard,
    CrewAnalysisResult,
    ProductionSettings,
    AuditionTask,
)
from src.actor_models import ActorProfile


class AppState:
    """单个浏览器会话的应用状态（不做模块级全局单例，避免多会话串数据）"""

    def __init__(self):
        self.llm_client = LLMClient()
        self.role_distiller = RoleDistiller(llm_client=self.llm_client)
        self.actor_profiler = ActorProfiler(llm_client=self.llm_client)
        self.matching_engine = MatchingEngine(llm_client=self.llm_client)
        self.crew_analyzer = CrewAnalyzer(llm_client=self.llm_client)
        self.audition_designer = AuditionDesigner(llm_client=self.llm_client)

        self.script_text = ""
        self.role_cards = []
        self.production_settings = ProductionSettings()
        self.audition_tasks = {}          # role_name -> AuditionTask
        self.actor_profiles = []
        self.casting_report = None
        self.crew_analysis = None

    def is_mock(self):
        return self.llm_client.is_mock_mode

    def role_names(self):
        return [c.role_name for c in self.role_cards]

    def actor_names(self):
        return [p.actor_name for p in self.actor_profiles]

    def invalidate_after_script_change(self):
        """剧本重新蒸馏后，清空所有下游产物并要求重新确认设定。"""
        self.actor_profiles = []
        self.casting_report = None
        self.crew_analysis = None
        self.audition_tasks = {}
        self.production_settings = ProductionSettings()

    def to_project_dict(self):
        return {
            "project": "CastingNuwa",
            "version": "0.6",
            "saved_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "script_text": self.script_text,
            "roles": [c.to_dict() for c in self.role_cards],
            "production_settings": self.production_settings.to_dict(),
            "audition_tasks": {
                name: task.to_dict() for name, task in self.audition_tasks.items()
            },
            "actors": [p.to_dict() for p in self.actor_profiles],
            "casting_report": self.casting_report.to_dict() if self.casting_report else None,
            "crew_analysis": self.crew_analysis.to_dict() if self.crew_analysis else None,
        }

    def load_project_dict(self, data):
        if not isinstance(data, dict):
            raise ValueError("项目文件格式不正确")

        self.script_text = data.get("script_text", "") or ""
        self.role_cards = [
            RoleCard.from_dict(item)
            for item in data.get("roles", []) if isinstance(item, dict)
        ]
        settings = data.get("production_settings")
        self.production_settings = (
            ProductionSettings.from_dict(settings)
            if isinstance(settings, dict) else ProductionSettings()
        )
        self.audition_tasks = {}
        for name, task_data in (data.get("audition_tasks", {}) or {}).items():
            if isinstance(task_data, dict):
                self.audition_tasks[name] = AuditionTask.from_dict(task_data)
        self.actor_profiles = [
            ActorProfile.from_dict(item)
            for item in data.get("actors", []) if isinstance(item, dict)
        ]
        report = data.get("casting_report")
        self.casting_report = (
            self.matching_engine_cls_report(report)
            if isinstance(report, dict) else None
        )
        crew = data.get("crew_analysis")
        self.crew_analysis = CrewAnalysisResult.from_dict(crew) if isinstance(crew, dict) else None

    @staticmethod
    def matching_engine_cls_report(report_dict):
        from src.matching_engine import CastingReport
        return CastingReport.from_dict(report_dict)


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
    """将演员观察记录格式化为 Markdown（观察记录优先，评分弱化）"""
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
    ])
    if getattr(profile, "schedule_info", ""):
        lines.append(f"**档期/可排练时间**：{profile.schedule_info}")
    lines.append("")

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
    """将单个候选方案格式化为 Markdown"""
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


def format_audition_task_markdown(task: AuditionTask) -> str:
    """将试镜任务格式化为可直接执行的 Markdown"""
    lines = [f"## 🎬 角色「{task.role_name}」两轮试镜任务", ""]

    if task.scene_description:
        lines.append("### 一、统一试镜场景")
        lines.append(task.scene_description)
        lines.append("")

    if task.script_excerpt:
        lines.append("### 二、试镜台词片段（1-2 分钟）")
        lines.append("> " + task.script_excerpt.replace("\n", "\n> "))
        lines.append("")

    if task.observation_focus:
        lines.append("### 三、观察重点（学生评委照着看）")
        lines.append("")
        for i, focus in enumerate(task.observation_focus, 1):
            lines.append(f"**{i}. {focus.focus}**")
            if focus.explanation:
                lines.append(f"- 说明：{focus.explanation}")
            if focus.positive_signals:
                lines.append(f"- ✅ 看到这些算好：{'；'.join(focus.positive_signals)}")
            if focus.negative_signals:
                lines.append(f"- ⚠️ 看到这些要警惕：{'；'.join(focus.negative_signals)}")
            lines.append("")

    if task.adjustment_instruction:
        lines.append("### 四、第一遍后的调整指令")
        lines.append(f"> {task.adjustment_instruction}")
        lines.append("")

    if task.retest_task:
        lines.append("### 五、第二遍复试")
        lines.append(f"- 复试任务：{task.retest_task}")
        if task.retest_focus:
            lines.append(f"- 复试重点：{task.retest_focus}")
        lines.append("")

    lines.append("> 复试用来区分「第一次碰巧合适」与「能理解并执行指导」，请记录两遍差异。")
    return "\n".join(lines)


def format_settings_markdown(settings: ProductionSettings) -> str:
    """展示选角设定与确认状态"""
    status = "✅ **已确认**（可以整理候选方案）" if settings.confirmed else "⛔ **尚未确认**（请核对后点击下方确认按钮）"
    lines = [
        "## ⚙️ 制作与选角设定",
        "",
        f"**状态**：{status}",
        "",
        f"- **表演风格**：{settings.performance_style or '未填写'}",
        f"- **导演阐述 / 角色理解**：{settings.role_interpretation or '未填写'}",
        f"- **接受反串**：{'是' if settings.allow_cross_gender else '否'}",
        f"- **接受兼角**：{'是' if settings.allow_double_casting else '否'}",
        f"- **档期 / 排练时间约束**：{settings.schedule_constraints or '未填写'}",
        "",
    ]
    lines.append("**🔴 必须满足的要求**")
    if settings.must_have_requirements:
        for item in settings.must_have_requirements:
            lines.append(f"- {item}")
    else:
        lines.append("- （无）")
    lines.append("")
    lines.append("**⚪ 可以通过排练改善的要求**")
    if settings.can_rehearse:
        for item in settings.can_rehearse:
            lines.append(f"- {item}")
    else:
        lines.append("- （无）")
    lines.append("")
    lines.append("> 注意：「角色内向」这类性格标签应转化为可观察的表演要求，而不是直接寻找内向的演员。")
    return "\n".join(lines)


def format_decision_table(report) -> str:
    """最终选角决定表（人工确认 + 理由）"""
    if not report or not report.results:
        return "### ✅ 最终选角决定表\n\n暂无候选方案，请先在本页整理全量候选方案。"
    lines = [
        "### ✅ 最终选角决定表",
        "",
        "| 角色 | 确认人选 | 确认理由 | 确认时间 |",
        "|------|----------|----------|----------|",
    ]
    for result in report.results:
        actor = result.confirmed_actor_name or "⏳ 待确认"
        reason = (result.confirmation_reason or "—").replace("|", "/").replace("\n", " ")
        at = result.confirmed_at or "—"
        lines.append(f"| {result.role_name} | {actor} | {reason} | {at} |")
    lines.append("")
    lines.append("> 最终人选由负责人结合试演、对手戏化学反应与档期决定，工具只整理依据。")
    return "\n".join(lines)


def error_notice(exc: Exception, where: str) -> str:
    return (
        f"🔴 **真实 AI 调用失败（{where}）**\n\n{str(exc)}\n\n"
        "请检查网络、API Key、额度或 Base URL 后重试；系统不会用演示数据冒充真实结果。"
    )


def role_dropdown_updates(state, include_actor=False):
    """生成各页角色/演员下拉的统一更新。"""
    role_names = state.role_names()
    role_upd = gr.update(choices=role_names, value=role_names[0] if role_names else None)
    updates = [role_upd, role_upd, role_upd, role_upd]
    if include_actor:
        actor_names = state.actor_names()
        actor_upd = gr.update(choices=actor_names, value=actor_names[0] if actor_names else None)
        updates = [role_upd, role_upd, role_upd, role_upd, actor_upd, actor_upd]
    return updates


# ============================================================
# 标签页 1：角色蒸馏
# ============================================================

def distill_roles(state, script_text):
    """角色蒸馏，并在剧本更新后重置下游、提示重算。"""
    empty = gr.update(choices=[], value=None)
    if state is None:
        state = AppState()
    if not script_text or not script_text.strip():
        return (state, "⚠️ 请输入剧本内容", "", empty, empty, empty, empty,
                format_settings_markdown(state.production_settings), "⚠️ 请先输入剧本。")

    try:
        role_cards = state.role_distiller.distill_all(script_text)
    except LLMServiceError as exc:
        return (state, error_notice(exc, "角色蒸馏"), "", empty, empty, empty, empty,
                format_settings_markdown(state.production_settings), "🔴 角色蒸馏未完成。")
    except Exception as exc:  # noqa: BLE001
        return (state, f"❌ 角色蒸馏出错：{exc}", "", empty, empty, empty, empty,
                format_settings_markdown(state.production_settings), "🔴 角色蒸馏未完成。")

    if not role_cards:
        return (state, "❌ 角色蒸馏失败，请检查剧本格式后重试。", "", empty, empty, empty, empty,
                format_settings_markdown(state.production_settings), "🔴 角色蒸馏未完成。")

    state.script_text = script_text
    state.role_cards = role_cards
    state.invalidate_after_script_change()

    parts = [
        f"### 蒸馏完成：共 {len(role_cards)} 个角色\n",
        "> 💡 下一步：到「② 选角设定」核对必须满足/可排练项并确认；",
        "> 再到「③ 试镜任务」生成两轮试镜，最后在「④ 演员观察」记录表现。",
        "",
    ]
    for card in role_cards:
        parts.append(format_role_card_markdown(card))
        parts.append("\n---\n")
    json_output = json.dumps({"roles": [c.to_dict() for c in role_cards]},
                             indent=2, ensure_ascii=False)

    notice = "🔴 剧本已更新：选角设定、试镜任务、演员观察与候选方案均已重置，请按 ②→③→④→⑤ 重新走一遍。"
    return (state, "\n".join(parts), json_output,
            *role_dropdown_updates(state),
            format_settings_markdown(state.production_settings), notice)


# ============================================================
# 标签页 2：选角设定
# ============================================================

def prefill_settings(state):
    """从所有角色卡的可观察要求预填必须满足/可排练两个文本框。"""
    if state is None:
        state = AppState()
    if not state.role_cards:
        return state, "", "", "⚠️ 请先在「① 角色蒸馏」生成角色卡。"
    must, rehearse = [], []
    for card in state.role_cards:
        for req in card.casting_guide.observable_requirements:
            line = f"[{card.role_name}] {req.requirement}"
            (must if req.must_have else rehearse).append(line)
    return state, "\n".join(must), "\n".join(rehearse), "已从角色卡预填，可自行增删修改。"


def _split_lines(text):
    return [line.strip(" -•\t") for line in (text or "").splitlines() if line.strip()]


def save_settings(state, style, interp, must_text, rehearse_text,
                  cross_gender, double_casting, schedule):
    if state is None:
        state = AppState()
    state.production_settings = ProductionSettings(
        performance_style=style or "",
        role_interpretation=interp or "",
        must_have_requirements=_split_lines(must_text),
        can_rehearse=_split_lines(rehearse_text),
        allow_cross_gender=bool(cross_gender),
        allow_double_casting=bool(double_casting),
        schedule_constraints=schedule or "",
        confirmed=True,
    )
    return state, format_settings_markdown(state.production_settings), "✅ 选角设定已保存并确认，可以整理候选方案。"


# ============================================================
# 标签页 3：试镜任务
# ============================================================

def design_one_audition(state, role_name):
    if state is None:
        state = AppState()
    if not state.role_cards:
        return state, "⚠️ 请先在「① 角色蒸馏」生成角色卡。", gr.update(), "⚠️ 缺少角色卡。"
    if not role_name:
        role_name = state.role_names()[0]
    card = next((c for c in state.role_cards if c.role_name == role_name), None)
    if card is None:
        return state, "❌ 未找到该角色。", gr.update(), "❌ 未找到角色。"
    try:
        task = state.audition_designer.design_for_role(
            card, state.script_text, state.production_settings
        )
    except LLMServiceError as exc:
        return state, error_notice(exc, "试镜任务设计"), gr.update(), "🔴 试镜任务生成失败。"
    except Exception as exc:  # noqa: BLE001
        return state, f"❌ 试镜任务生成出错：{exc}", gr.update(), "🔴 试镜任务生成失败。"
    state.audition_tasks[card.role_name] = task
    names = state.role_names()
    return (state, format_audition_task_markdown(task),
            gr.update(choices=names, value=card.role_name),
            f"✅ 已生成「{card.role_name}」试镜任务。")


def design_all_auditions(state):
    if state is None:
        state = AppState()
    if not state.role_cards:
        return state, "⚠️ 请先在「① 角色蒸馏」生成角色卡。", gr.update(), "⚠️ 缺少角色卡。"
    try:
        tasks = state.audition_designer.design_all(
            state.role_cards, state.script_text, state.production_settings
        )
    except LLMServiceError as exc:
        return state, error_notice(exc, "试镜任务设计"), gr.update(), "🔴 试镜任务生成失败。"
    except Exception as exc:  # noqa: BLE001
        return state, f"❌ 试镜任务生成出错：{exc}", gr.update(), "🔴 试镜任务生成失败。"
    for task in tasks:
        state.audition_tasks[task.role_name] = task
    parts = [f"### 已为 {len(tasks)} 个角色生成两轮试镜任务\n"]
    for task in tasks:
        parts.append(format_audition_task_markdown(task))
        parts.append("\n---\n")
    names = state.role_names()
    return (state, "\n".join(parts), gr.update(choices=names, value=names[0] if names else None),
            f"✅ 已生成全部 {len(tasks)} 个角色的试镜任务。")


def export_auditions(state):
    if state is None:
        state = AppState()
    if not state.audition_tasks:
        return None, "⚠️ 还没有试镜任务，请先生成。"
    os.makedirs("output", exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join("output", f"试镜任务_{stamp}.md")
    parts = ["# 两轮试镜任务\n"]
    for task in state.audition_tasks.values():
        parts.append(format_audition_task_markdown(task))
        parts.append("\n---\n")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(parts))
    return path, f"✅ 已导出：{path}"


# ============================================================
# 标签页 4：演员观察
# ============================================================

def build_role_requirements_text(state, role_name):
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


def _split_blocks(text):
    if not text or not text.strip():
        return []
    return [b for b in re.split(r'\n---\s*\n', text.strip()) if b.strip()]


def profile_actors(state, actor_text, target_role_name, adjustment_text,
                   second_round_text, schedule_text):
    if state is None:
        state = AppState()
    if not actor_text or not actor_text.strip():
        empty = gr.update(choices=state.actor_names())
        return state, "⚠️ 请输入演员材料", "", empty, empty, "⚠️ 缺少演员材料。"

    role_requirements = build_role_requirements_text(state, target_role_name)
    blocks = _split_blocks(actor_text)
    adjust_blocks = _split_blocks(adjustment_text)
    second_blocks = _split_blocks(second_round_text)

    profiles = []
    try:
        for index, block in enumerate(blocks):
            name_match = re.search(r'【演员[^】]*[:：]\s*([^】]+)】', block)
            actor_name = name_match.group(1).strip() if name_match else f"演员{index + 1}"

            schedule_match = re.search(r'档期[:：]\s*([^\n】]+)', block)
            if schedule_match:
                schedule_info = schedule_match.group(1).strip()
            elif len(blocks) == 1 and schedule_text:
                schedule_info = schedule_text.strip()
            else:
                schedule_info = ""

            adjustment = (
                adjust_blocks[index] if index < len(adjust_blocks)
                else (adjust_blocks[0] if adjust_blocks else "")
            )
            second_round = second_blocks[index] if index < len(second_blocks) else ""

            profile = state.actor_profiler.profile_from_text(
                actor_material=block,
                actor_name=actor_name,
                role_requirements=role_requirements,
                adjustment_instruction=adjustment,
                second_round_material=second_round,
                schedule_info=schedule_info,
            )
            if profile:
                profiles.append(profile)
    except LLMServiceError as exc:
        actor_upd = gr.update(choices=state.actor_names())
        return (state, error_notice(exc, "演员观察"), "", actor_upd, actor_upd,
                "🔴 演员观察未完成，未保存本次结果。")
    except Exception as exc:  # noqa: BLE001
        actor_upd = gr.update(choices=state.actor_names())
        return (state, f"❌ 演员观察出错：{exc}", "", actor_upd, actor_upd, "🔴 演员观察未完成。")

    if not profiles:
        actor_upd = gr.update(choices=state.actor_names())
        return state, "❌ 演员观察记录生成失败", "", actor_upd, actor_upd, "🔴 未生成观察记录。"

    state.actor_profiles = profiles
    state.casting_report = None

    parts = [f"### 观察记录完成：共 {len(profiles)} 位演员\n"]
    for profile in profiles:
        parts.append(format_actor_profile_markdown(profile))
        parts.append("\n---\n")
    json_output = json.dumps({"actors": [p.to_dict() for p in profiles]},
                             indent=2, ensure_ascii=False)
    actor_names = state.actor_names()
    actor_upd = gr.update(choices=actor_names, value=actor_names[0] if actor_names else None)
    return (state, "\n".join(parts), json_output, actor_upd, actor_upd,
            f"✅ 已记录 {len(profiles)} 位演员，可到「⑤ 候选方案」整理。")


def _append_media_profile(state, profile, error_prefix):
    if profile is None:
        actor_upd = gr.update(choices=state.actor_names())
        return None, f"{error_prefix}分析失败。", "", actor_upd, actor_upd, "🔴 分析失败。"
    state.actor_profiles.append(profile)
    state.casting_report = None
    actor_names = state.actor_names()
    actor_upd = gr.update(choices=actor_names, value=profile.actor_name)
    return (format_actor_profile_markdown(profile), profile.to_json(),
            actor_upd, actor_upd, f"✅ 已加入演员：{profile.actor_name}")


def profile_from_video_file(state, video_path, actor_name, text_material):
    if state is None:
        state = AppState()
    if not video_path:
        return state, "⚠️ 请先上传视频文件", "", gr.update(), gr.update(), "⚠️ 缺少视频。"
    try:
        profile = state.actor_profiler.profile_from_video(
            video_path=video_path, actor_name=actor_name or "视频演员",
            text_material=text_material or "",
        )
        packed = _append_media_profile(state, profile, "视频")
        if packed[0] is None:
            return state, packed[1], packed[2], packed[3], packed[4], packed[5]
        return state, packed[0], packed[1], packed[2], packed[3], packed[5]
    except LLMServiceError as exc:
        actor_upd = gr.update(choices=state.actor_names())
        return state, error_notice(exc, "视频观察"), "", actor_upd, actor_upd, "🔴 视频观察失败。"
    except Exception as exc:  # noqa: BLE001
        import traceback
        actor_upd = gr.update(choices=state.actor_names())
        msg = f"❌ 视频处理出错：{exc}\n\n{traceback.format_exc()}"
        return state, msg, "", actor_upd, actor_upd, "🔴 视频处理出错。"


def profile_from_audio_file(state, audio_path, actor_name, text_material):
    if state is None:
        state = AppState()
    if not audio_path:
        return state, "⚠️ 请先上传音频文件", "", gr.update(), gr.update(), "⚠️ 缺少音频。"
    try:
        profile = state.actor_profiler.profile_from_audio(
            audio_path=audio_path, actor_name=actor_name or "音频演员",
            text_material=text_material or "",
        )
        packed = _append_media_profile(state, profile, "音频")
        if packed[0] is None:
            return state, packed[1], packed[2], packed[3], packed[4], packed[5]
        return state, packed[0], packed[1], packed[2], packed[3], packed[5]
    except LLMServiceError as exc:
        actor_upd = gr.update(choices=state.actor_names())
        return state, error_notice(exc, "音频观察"), "", actor_upd, actor_upd, "🔴 音频观察失败。"
    except Exception as exc:  # noqa: BLE001
        import traceback
        actor_upd = gr.update(choices=state.actor_names())
        return (state, f"❌ 音频处理出错：{exc}\n\n{traceback.format_exc()}",
                "", actor_upd, actor_upd, "🔴 音频处理出错。")


# ============================================================
# 标签页 5：候选方案 + 人工确认
# ============================================================

def match_single(state, role_name, actor_name):
    if state is None:
        state = AppState()
    if not role_name or not actor_name:
        return "⚠️ 请先生成角色卡和演员观察记录，并在上方选择角色与演员。", "⚠️ 信息不全。"
    role = next((r for r in state.role_cards if r.role_name == role_name), None)
    actor = next((a for a in state.actor_profiles if a.actor_name == actor_name), None)
    if not role or not actor:
        return "❌ 未找到对应的角色卡或演员观察记录。", "❌ 数据缺失。"
    try:
        proposal = state.matching_engine.match_one(
            role, actor, production_settings=state.production_settings
        )
    except LLMServiceError as exc:
        return error_notice(exc, "候选方案"), "🔴 候选方案生成失败。"
    except Exception as exc:  # noqa: BLE001
        return f"❌ 候选方案生成出错：{exc}", "🔴 候选方案生成失败。"
    if not proposal:
        return "❌ 候选方案生成失败。", "🔌 候选方案生成失败。"
    return format_proposal_markdown(proposal, role_name=role_name), f"✅ 已生成「{role_name} × {actor_name}」候选方案。"


def render_full_report(report) -> str:
    lines = [
        "## 📋 选角候选方案报告",
        "",
        f"**角色数**：{report.role_count} | **演员数**：{report.actor_count}",
        "",
        "> ⚠️ 本报告**不是排名**，而是按角色的可观察要求逐条核对证据，",
        "> 帮助导演决定谁优先试演、谁需要补充试镜。最终判断权在导演。",
        "",
        "### 🗺️ 候选概览",
        "",
        "| 角色 | 优先试演 | 需补充试镜 | 明确限制 |",
        "|------|----------|-----------|----------|",
    ]
    for result in report.results:
        priority = [p.actor_name for p in result.proposals if p.category == "priority_audition"]
        more = [p.actor_name for p in result.proposals if p.category == "needs_more_audition"]
        limit = [p.actor_name for p in result.proposals if p.category == "explicit_limit"]
        lines.append(
            f"| {result.role_name} | "
            f"{', '.join(priority) or '—'} | "
            f"{', '.join(more) or '—'} | "
            f"{', '.join(limit) or '—'} |"
        )
    lines.append("")
    lines.append("### 📝 分角色候选方案")
    lines.append("")
    for result in report.results:
        lines.append(f"## 🎭 角色：{result.role_name}")
        lines.append("")
        for proposal in result.proposals:
            lines.append(format_proposal_markdown(proposal, role_name=result.role_name))
            lines.append("")
        if result.chemistry_checks:
            lines.append("**🧪 化学反应验证（单人试镜无法判断，需安排对手戏）**")
            for check in result.chemistry_checks:
                lines.append(f"- {check}")
            lines.append("")
        lines.append("---")
        lines.append("")
    if report.global_notes:
        lines.append("### ⚠️ 兼角 / 档期等全局说明")
        for note in report.global_notes:
            lines.append(f"- {note}")
        lines.append("")
    return "\n".join(lines)


def run_full_matching(state):
    placeholder_dd = gr.update()
    if state is None:
        state = AppState()
    if not state.role_cards or not state.actor_profiles:
        return (state, "⚠️ 请先完成「① 角色蒸馏」和「④ 演员观察」。", "",
                placeholder_dd, format_decision_table(None), "⚠️ 前置数据不全。")
    if not state.production_settings.confirmed:
        return (state,
                "⛔ 请先到「② 选角设定」核对并**确认**选角设定（必须满足项、反串/兼角、档期），再整理候选方案。",
                "", placeholder_dd, format_decision_table(None),
                "⛔ 选角设定尚未确认。")
    try:
        report = state.matching_engine.match_all(
            state.role_cards, state.actor_profiles,
            production_settings=state.production_settings,
        )
    except LLMServiceError as exc:
        return (state, error_notice(exc, "候选方案"), "", placeholder_dd,
                format_decision_table(state.casting_report), "🔴 候选方案整理失败。")
    except Exception as exc:  # noqa: BLE001
        return (state, f"❌ 候选方案整理出错：{exc}", "", placeholder_dd,
                format_decision_table(state.casting_report), "🔴 候选方案整理失败。")

    state.casting_report = report
    role_names = state.role_names()
    confirm_role_dd = gr.update(choices=role_names, value=role_names[0] if role_names else None)
    return (state, render_full_report(report), report.to_json(),
            confirm_role_dd, format_decision_table(report), "✅ 候选方案已整理，可在下方确认最终人选。")


def update_confirm_actors(state, role_name):
    if state is None or not state.casting_report or not role_name:
        return gr.update()
    result = state.casting_report.get_result_for_role(role_name)
    if not result:
        return gr.update()
    names = [p.actor_name for p in result.proposals]
    current = result.confirmed_actor_name or (names[0] if names else None)
    return gr.update(choices=names, value=current)


def confirm_decision(state, role_name, actor_name, reason):
    if state is None:
        state = AppState()
    if not state.casting_report or not role_name:
        return state, format_decision_table(None), gr.update(), "⚠️ 请先整理全量候选方案。"
    ok = state.casting_report.confirm_actor(role_name, actor_name, reason.strip())
    if not ok:
        actor_dd = update_confirm_actors(state, role_name)
        return state, format_decision_table(state.casting_report), actor_dd, "❌ 确认失败：该演员不在此角色候选中。"
    actor_dd = update_confirm_actors(state, role_name)
    who = actor_name or "（暂不指定，留空待试演）"
    return (state, format_decision_table(state.casting_report), actor_dd,
            f"✅ 已确认「{role_name}」→ {who}，理由已保存。")


# ============================================================
# 标签页 6：制作团队
# ============================================================

def analyze_crew(state, script_text):
    if state is None:
        state = AppState()
    if not script_text or not script_text.strip():
        return state, "⚠️ 请输入剧本内容", "", "⚠️ 缺少剧本。"
    try:
        analysis = state.crew_analyzer.analyze(script_text)
        state.crew_analysis = analysis
        return state, format_crew_analysis_markdown(analysis), analysis.to_json(), "✅ 制作团队需求分析完成。"
    except LLMServiceError as exc:
        return state, error_notice(exc, "制作团队分析"), "", "🔴 团队分析失败。"
    except Exception as exc:  # noqa: BLE001
        return state, f"❌ 分析失败：{exc}", "", "🔌 团队分析出错。"


# ============================================================
# 项目保存 / 加载（会话隔离 + 可复核存档）
# ============================================================

def save_project(state):
    if state is None:
        state = AppState()
    if not state.role_cards and not state.actor_profiles:
        return None, "⚠️ 当前没有可保存的内容。"
    os.makedirs("output", exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join("output", f"casting_project_{stamp}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(state.to_project_dict(), f, ensure_ascii=False, indent=2)
    return path, f"✅ 项目已保存：{path}"


def load_project(state, file_path):
    if state is None:
        state = AppState()
    if not file_path:
        return [state] + [gr.update()] * 22 + ["⚠️ 未选择文件。"]
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        state.load_project_dict(data)
    except Exception as exc:  # noqa: BLE001
        return [state] + [gr.update()] * 22 + [f"❌ 项目加载失败：{exc}"]

    role_names = state.role_names()
    actor_names = state.actor_names()
    role_dd = gr.update(choices=role_names, value=role_names[0] if role_names else None)
    actor_dd = gr.update(choices=actor_names, value=actor_names[0] if actor_names else None)

    role_md = "\n".join(
        format_role_card_markdown(c) + "\n\n---\n" for c in state.role_cards
    ) or "暂无角色卡。"
    actor_md = "\n".join(
        format_actor_profile_markdown(p) + "\n\n---\n" for p in state.actor_profiles
    ) or "暂无演员观察记录。"
    audition_md = "\n".join(
        format_audition_task_markdown(t) + "\n\n---\n"
        for t in state.audition_tasks.values()
    ) or "暂无试镜任务。"
    report_md = render_full_report(state.casting_report) if state.casting_report else "暂无候选方案。"
    crew_md = format_crew_analysis_markdown(state.crew_analysis) if state.crew_analysis else "暂无制作团队分析。"

    settings = state.production_settings
    return [
        state,
        state.script_text,
        role_md,
        json.dumps({"roles": [c.to_dict() for c in state.role_cards]}, ensure_ascii=False, indent=2),
        role_dd, role_dd, role_dd, role_dd,
        actor_md, actor_dd, actor_dd,
        format_settings_markdown(settings),
        settings.performance_style,
        settings.role_interpretation,
        "\n".join(settings.must_have_requirements),
        "\n".join(settings.can_rehearse),
        settings.allow_cross_gender,
        settings.allow_double_casting,
        settings.schedule_constraints,
        audition_md,
        report_md,
        format_decision_table(state.casting_report),
        crew_md,
        f"✅ 项目已加载：{len(role_names)} 个角色、{len(actor_names)} 位演员。",
    ]


# ============================================================
# Gradio 界面构建
# ============================================================

def refresh_dropdowns(state):
    """刷新各页角色/演员下拉。"""
    if state is None:
        state = AppState()
    role_names = state.role_names()
    actor_names = state.actor_names()
    role_upd = gr.update(choices=role_names, value=role_names[0] if role_names else None)
    actor_upd = gr.update(choices=actor_names, value=actor_names[0] if actor_names else None)
    return role_upd, actor_upd, role_upd, role_upd, role_upd, actor_upd


def build_ui():
    """构建 Gradio 界面（v0.6 引导式选角流程）"""
    demo_mode = LLMClient().is_mock_mode

    with gr.Blocks(title="CastingNuwa · 选角女娲") as demo:
        app_state = gr.State(value=None)

        gr.Markdown("# 🎭 CastingNuwa · 选角女娲", elem_classes="main-title")
        gr.Markdown("### 引导学生剧团完成一轮有依据、可复核的选角", elem_classes="subtitle")
        gr.Markdown(
            "女娲造人，我们造角色卡。系统不替导演打分下结论，"
            "而是按 **① 角色蒸馏 → ② 选角设定 → ③ 试镜任务 → ④ 演员观察 → ⑤ 候选与确认** "
            "引导你走完选角，并保存每一步的依据。"
        )

        if demo_mode:
            gr.Markdown(
                "⚠️ **当前为演示模式**：未配置 LLM API Key，输出为示例数据（页面会明确标注 demo，不能作为选角依据）。"
                "配置 `LLM_API_KEY` 后使用真实 AI；真实调用失败会明确报错，不会用假数据冒充。",
                elem_classes="mock-banner",
            )

        with gr.Row():
            save_project_btn = gr.Button("💾 保存项目（下载 JSON）", variant="secondary", size="sm")
            project_file = gr.File(label="项目存档", visible=True, height=100)
            load_project_file = gr.File(
                label="加载项目（上传 .json）", file_types=[".json"], type="filepath", height=100,
            )

        global_notice = gr.Markdown("")

        with gr.Tabs():

            # ===== ① 角色蒸馏 =====
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
                            distill_btn = gr.Button("🎭 开始角色蒸馏", variant="primary")
                    with gr.Column(scale=1):
                        role_output = gr.Markdown(label="角色卡结果")
                        role_json = gr.Code(label="JSON 输出", language="json")

            # ===== ② 选角设定 =====
            with gr.Tab("② 选角设定"):
                gr.Markdown(
                    "### 第 2 步：把创作选择讲清楚，负责人确认后才进入匹配"
                )
                gr.Markdown(
                    "> 剧本不能决定所有选角。这里登记表演风格、必须满足 vs 可排练项、"
                    "反串/兼角与档期；可先从角色卡预填可观察要求再修改。"
                )
                with gr.Row():
                    with gr.Column(scale=1):
                        settings_style = gr.Textbox(label="剧团希望的表演风格", lines=2)
                        settings_interp = gr.Textbox(label="导演阐述 / 对角色的理解", lines=3)
                        prefill_btn = gr.Button("📥 从角色卡预填可观察要求", variant="secondary")
                        settings_must = gr.Textbox(
                            label="🔴 必须满足的要求（每行一条）", lines=6,
                            placeholder="这些要求不能靠排练弥补，初筛就要满足...",
                        )
                        settings_rehearse = gr.Textbox(
                            label="⚪ 可以通过排练改善的要求（每行一条）", lines=6,
                        )
                        with gr.Row():
                            settings_cross = gr.Checkbox(label="接受反串")
                            settings_double = gr.Checkbox(label="接受兼角")
                        settings_schedule = gr.Textbox(
                            label="档期 / 排练时间约束", lines=2,
                            placeholder="如：每周三晚、周日全天排练，11月15日演出...",
                        )
                        save_settings_btn = gr.Button("✅ 保存并确认选角设定", variant="primary")
                    with gr.Column(scale=1):
                        settings_status = gr.Markdown(format_settings_markdown(ProductionSettings()))

            # ===== ③ 试镜任务 =====
            with gr.Tab("③ 试镜任务"):
                gr.Markdown("### 第 3 步：根据角色要求生成**两轮试镜任务**")
                gr.Markdown(
                    "> 统一试镜材料 + 2-3 个观察重点 + 一条调整指令 + 复试任务，"
                    "让没经验的评委也知道让演员演什么、在旁边看什么。"
                )
                with gr.Row():
                    audition_role_dd = gr.Dropdown(label="选择角色", choices=[], interactive=True, scale=2)
                    design_one_btn = gr.Button("🎬 生成该角色试镜任务", variant="primary")
                    design_all_btn = gr.Button("📚 生成全部角色", variant="secondary")
                    export_btn = gr.Button("📤 导出试镜任务", variant="secondary")
                audition_file = gr.File(label="试镜任务导出", visible=True)
                audition_output = gr.Markdown("尚未生成试镜任务。")

            # ===== ④ 演员观察 =====
            with gr.Tab("④ 演员观察"):
                gr.Markdown("### 第 4 步：记录试镜表现，输出**观察记录**而非演技打分")
                gr.Markdown(
                    "> 每条观察：发生了什么（时间戳）→ 可能意味着什么（保留其他解释）"
                    "→ 依据类型 → 下一轮怎么验证。材料不足生成**待验证项**，不硬给中等分。"
                )
                with gr.Tabs():
                    with gr.Tab("📝 文本模式（支持两轮复试）"):
                        with gr.Row():
                            with gr.Column(scale=1):
                                profile_role_dd = gr.Dropdown(
                                    label="对照角色（建议先完成①②③）", choices=[], interactive=True,
                                )
                                actor_input = gr.Textbox(
                                    label="第一遍试镜材料（自我介绍+转写）",
                                    placeholder="多位演员用单独一行 --- 分隔。",
                                    lines=12, value=load_example_actors(),
                                )
                                adjustment_input = gr.Textbox(
                                    label="第一遍后的调整指令（可选）", lines=2,
                                    placeholder="如：这次你非常想让对方留下，但不能让对方察觉。多演员用 --- 分隔。",
                                )
                                second_round_input = gr.Textbox(
                                    label="第二遍（复试）表现记录（可选）", lines=6,
                                    placeholder="填写后会输出指导后复试对比；多演员用 --- 分隔，顺序与第一遍一致。",
                                )
                                schedule_input = gr.Textbox(
                                    label="演员档期/可排练时间（单演员；多演员请在材料内写“档期：…”）", lines=1,
                                )
                                with gr.Row():
                                    load_actor_btn = gr.Button("📄 加载示例", variant="secondary")
                                    clear_actor_btn = gr.Button("🗑️ 清空", variant="secondary")
                                    profile_btn = gr.Button("🎬 生成观察记录", variant="primary")
                            with gr.Column(scale=1):
                                actor_output = gr.Markdown("尚未生成演员观察记录。")
                                actor_json = gr.Code(label="JSON 输出", language="json")

                    with gr.Tab("🎥 视频模式（三模态）"):
                        gr.Markdown(
                            "视频按**全片均匀采样**并保留时间戳；声音/动作变化只是线索，"
                            "不直接等同于演得好。"
                        )
                        with gr.Row():
                            with gr.Column(scale=1):
                                video_actor_name = gr.Textbox(label="演员姓名（可选）")
                                video_upload = gr.Video(label="上传试镜视频", sources=["upload"])
                                video_extra_text = gr.Textbox(label="额外文本材料（可选）", lines=3)
                                video_profile_btn = gr.Button("🎬 从视频生成观察记录", variant="primary")
                            with gr.Column(scale=1):
                                video_output = gr.Markdown("尚未分析视频。")
                                video_json = gr.Code(label="JSON 输出", language="json")

                    with gr.Tab("🎵 音频模式（双模态）"):
                        with gr.Row():
                            with gr.Column(scale=1):
                                audio_actor_name = gr.Textbox(label="演员姓名（可选）")
                                audio_upload = gr.Audio(label="上传试镜音频", sources=["upload"], type="filepath")
                                audio_extra_text = gr.Textbox(label="额外文本材料（可选）", lines=3)
                                audio_profile_btn = gr.Button("🎬 从音频生成观察记录", variant="primary")
                            with gr.Column(scale=1):
                                audio_output = gr.Markdown("尚未分析音频。")
                                audio_json = gr.Code(label="JSON 输出", language="json")

            # ===== ⑤ 候选方案与人工确认 =====
            with gr.Tab("⑤ 候选与确认"):
                gr.Markdown("### 第 5 步：逐条核对证据，整理候选并**人工确认最终人选**")
                gr.Markdown(
                    "> 🟢 优先试演 / 🟡 补充试镜 / 🔴 明确限制。需先在「② 选角设定」确认；"
                    "单人试镜无法判断化学反应，会建议安排对手戏。"
                )
                with gr.Row():
                    with gr.Column(scale=1):
                        match_role_dd = gr.Dropdown(label="选择角色", choices=[], interactive=True)
                        match_actor_dd = gr.Dropdown(label="选择演员（单个对照）", choices=[], interactive=True)
                        with gr.Row():
                            refresh_btn = gr.Button("🔄 刷新列表", variant="secondary")
                            match_btn = gr.Button("🎯 单个候选方案", variant="secondary")
                        full_match_btn = gr.Button("📋 整理全量候选方案", variant="primary")
                        gr.Markdown("---")
                        gr.Markdown("**人工确认最终人选**")
                        confirm_role_dd = gr.Dropdown(label="角色", choices=[], interactive=True)
                        confirm_actor_dd = gr.Dropdown(label="人选（来自该角色候选）", choices=[], interactive=True)
                        confirm_reason = gr.Textbox(label="确认理由（可写试演/化学反应/档期依据）", lines=2)
                        confirm_btn = gr.Button("✅ 确认该角色人选", variant="primary")
                    with gr.Column(scale=2):
                        match_output = gr.Markdown("尚未整理候选方案。")
                        match_json = gr.Code(label="JSON", language="json", visible=False)
                        decision_table = gr.Markdown(format_decision_table(None))

            # ===== ⑥ 制作团队 =====
            with gr.Tab("⑥ 制作团队分析"):
                gr.Markdown("### 输入剧本，分析所需的后台岗位与人员配置")
                gr.Markdown("支持：灯光师、音效师、舞美设计、服装师、道具师、化妆师")
                with gr.Row():
                    with gr.Column(scale=1):
                        crew_script_input = gr.Textbox(
                            label="剧本内容",
                            placeholder="粘贴剧本，包含舞台指示、场景描述、灯光/音效提示等...",
                            lines=16,
                        )
                        with gr.Row():
                            crew_load_example_btn = gr.Button("📄 加载示例剧本", variant="secondary")
                            crew_analyze_btn = gr.Button("🔍 分析制作团队需求", variant="primary")
                    with gr.Column(scale=2):
                        crew_output = gr.Markdown("尚未分析制作团队需求。")
                        with gr.Accordion("📋 JSON 原始数据", open=False):
                            crew_json_output = gr.Code(label="JSON", language="json")

            # ===== ⑦ 关于 =====
            with gr.Tab("ℹ️ 关于"):
                gr.Markdown("""
                ## CastingNuwa · 选角女娲（v0.6 引导式选角流程）

                ### 解决什么问题
                学生剧团选角常依赖导演个人直觉，角色描述与实际配置之间存在信息断层，
                导致初筛效率低、依据难复核。本工具不替导演做决定，而是**把选角过程结构化、可追溯**。

                ### 核心原则：AI 整理观察，而不是鉴定演技
                - **特征强度 ≠ 表演质量 ≠ 角色匹配**：外放程度是风格，不是演技好坏。
                - **性格标签 → 可观察表演要求**：「角色内向」转化为「通过停顿、回避目光让观众理解」。
                - **观察四要素**：发生了什么 → 可能意味着什么（保留其他解释）→ 依据是否充分 → 下一轮怎么验证。
                - **材料不足给待验证项，不硬给中等分**；自述「擅长」不等于「已展示能力」。
                - **两轮试镜**：统一材料演一遍 → 给明确调整指令 → 复试，区分「碰巧合适」与「能执行指导」。

                ### 工作流程
                1. **角色蒸馏**：剧本 → 角色卡与可观察表演要求
                2. **选角设定**：表演风格 / 必须满足 / 可排练 / 反串兼角 / 档期，负责人确认
                3. **试镜任务**：统一材料 + 观察重点 + 调整指令 + 复试任务
                4. **演员观察**：文本/音频/视频 → 观察记录与待验证项（支持两轮复试）
                5. **候选与确认**：证据对照 → 三类候选 + 兼角/档期/对手戏检查 → 人工确认并保存理由
                6. **制作团队**：剧本 → 灯光/音效/舞美/服装/道具/化妆岗位需求

                ### 工程与数据
                - 每个浏览器会话相互隔离；项目可保存为 JSON、可重新加载
                - 真实 AI 调用失败会**明确报错**，不会静默用演示数据冒充真实结果
                - 视频全片均匀采样并保留时间戳；MediaPipe 不可用时优雅降级并标注
                - 灵感来自 GitHub 开源项目 [nuwa-skill](https://github.com/alchaincyf/nuwa-skill)
                - LLM：OpenAI 兼容 API；多模态：faster-whisper / librosa / MediaPipe·OpenCV；Web：Gradio
                """)

        gr.Markdown("---")
        gr.Markdown("*CastingNuwa · 选角女娲 v0.6 | 引导有依据、可复核的戏剧选角，AI 整理观察而非替代判断*")

        # ---------------- 事件绑定（所有组件已创建，可跨页引用） ----------------
        load_example_btn.click(fn=load_example_script, outputs=script_input)
        clear_btn.click(fn=lambda: "", outputs=script_input)
        crew_load_example_btn.click(fn=load_example_script, outputs=crew_script_input)
        load_actor_btn.click(fn=load_example_actors, outputs=actor_input)
        clear_actor_btn.click(fn=lambda: "", outputs=actor_input)

        distill_btn.click(
            fn=distill_roles,
            inputs=[app_state, script_input],
            outputs=[app_state, role_output, role_json,
                     profile_role_dd, audition_role_dd, match_role_dd, confirm_role_dd,
                     settings_status, global_notice],
        )

        prefill_btn.click(
            fn=prefill_settings,
            inputs=[app_state],
            outputs=[app_state, settings_must, settings_rehearse, global_notice],
        )
        save_settings_btn.click(
            fn=save_settings,
            inputs=[app_state, settings_style, settings_interp, settings_must,
                    settings_rehearse, settings_cross, settings_double, settings_schedule],
            outputs=[app_state, settings_status, global_notice],
        )

        design_one_btn.click(
            fn=design_one_audition,
            inputs=[app_state, audition_role_dd],
            outputs=[app_state, audition_output, audition_role_dd, global_notice],
        )
        design_all_btn.click(
            fn=design_all_auditions,
            inputs=[app_state],
            outputs=[app_state, audition_output, audition_role_dd, global_notice],
        )
        export_btn.click(fn=export_auditions, inputs=[app_state],
                        outputs=[audition_file, global_notice])

        profile_btn.click(
            fn=profile_actors,
            inputs=[app_state, actor_input, profile_role_dd,
                    adjustment_input, second_round_input, schedule_input],
            outputs=[app_state, actor_output, actor_json,
                     match_actor_dd, confirm_actor_dd, global_notice],
        )
        video_profile_btn.click(
            fn=profile_from_video_file,
            inputs=[app_state, video_upload, video_actor_name, video_extra_text],
            outputs=[app_state, video_output, video_json,
                     match_actor_dd, confirm_actor_dd, global_notice],
        )
        audio_profile_btn.click(
            fn=profile_from_audio_file,
            inputs=[app_state, audio_upload, audio_actor_name, audio_extra_text],
            outputs=[app_state, audio_output, audio_json,
                     match_actor_dd, confirm_actor_dd, global_notice],
        )

        refresh_btn.click(
            fn=refresh_dropdowns, inputs=[app_state],
            outputs=[match_role_dd, match_actor_dd, profile_role_dd,
                     audition_role_dd, confirm_role_dd, confirm_actor_dd],
        )
        match_btn.click(
            fn=match_single, inputs=[app_state, match_role_dd, match_actor_dd],
            outputs=[match_output, global_notice],
        )
        full_match_btn.click(
            fn=run_full_matching, inputs=[app_state],
            outputs=[app_state, match_output, match_json,
                     confirm_role_dd, decision_table, global_notice],
        )
        confirm_role_dd.change(
            fn=update_confirm_actors, inputs=[app_state, confirm_role_dd],
            outputs=[confirm_actor_dd],
        )
        confirm_btn.click(
            fn=confirm_decision,
            inputs=[app_state, confirm_role_dd, confirm_actor_dd, confirm_reason],
            outputs=[app_state, decision_table, confirm_actor_dd, global_notice],
        )

        crew_analyze_btn.click(
            fn=analyze_crew, inputs=[app_state, crew_script_input],
            outputs=[app_state, crew_output, crew_json_output, global_notice],
        )

        save_project_btn.click(
            fn=save_project, inputs=[app_state], outputs=[project_file, global_notice],
        )
        load_project_file.change(
            fn=load_project, inputs=[app_state, load_project_file],
            outputs=[app_state, script_input, role_output, role_json,
                     profile_role_dd, audition_role_dd, match_role_dd, confirm_role_dd,
                     actor_output, match_actor_dd, confirm_actor_dd,
                     settings_status, settings_style, settings_interp, settings_must,
                     settings_rehearse, settings_cross, settings_double, settings_schedule,
                     audition_output, match_output, decision_table,
                     crew_output, global_notice],
        )

    return demo


if __name__ == "__main__":
    app = build_ui()
    app.launch(
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
