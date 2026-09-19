"""
CastingNuwa · 选角女娲
匹配引擎（Matching Engine）v0.5

核心变化：
- 从"单一排名分数"改为"候选方案+证据比较+待验证项"
- 基于角色的可观察表演要求，逐条比较演员的观察证据
- 输出分类：值得优先试演 / 需要补充试镜 / 存在明确限制
- 数值匹配降级为快速参考，不作为选角结论中心
"""

import os
import json
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict, Any

from .models import RoleCard, QUANTITATIVE_TRAITS, ObservableRequirement, ProductionSettings
from .actor_models import ActorProfile, ObservationRecord, VerificationItem
from .llm_client import LLMClient


# ============================================================
# 候选方案数据模型（v0.5）
# ============================================================

@dataclass
class EvidenceComparison:
    """单条角色要求的证据比较"""
    requirement: str = ""              # 角色要求（可观察表演要求）
    must_have: bool = False            # 是否硬性要求
    actor_evidence: List[str] = field(default_factory=list)  # 演员的观察证据
    evidence_status: str = "missing"   # supported（有证据支持）/ partial（部分支持）/ missing（缺失）/ contradicted（相反证据）
    notes: str = ""                    # 说明


@dataclass
class CastingProposal:
    """
    候选方案（替代旧的单一匹配分数）

    分类：
    - priority_audition：值得优先试演（有证据支持关键要求）
    - needs_more_audition：需要补充试镜（缺关键证据）
    - explicit_limit：存在明确限制（档期/硬性要求不满足等）
    """
    actor_name: str = ""
    category: str = "needs_more_audition"
    supported_requirements: List[str] = field(default_factory=list)  # 有证据支持的要求
    partial_requirements: List[str] = field(default_factory=list)    # 部分支持的要求
    missing_evidence: List[str] = field(default_factory=list)        # 缺什么证据
    explicit_limits: List[str] = field(default_factory=list)         # 明确限制
    tradeoffs: str = ""                # 方案取舍（谁稳定 vs 谁指导后改善明显）
    stability_note: str = ""           # 当前表现稳定性
    adjustment_note: str = ""          # 指导后改善情况
    next_steps: List[str] = field(default_factory=list)  # 下一步建议
    reference_score: float = 0.0       # 数值参考分（不作为主要依据）
    evidence_comparisons: List[EvidenceComparison] = field(default_factory=list)  # 逐条证据比较


@dataclass
class RoleCastingResult:
    """单个角色的选角结果"""
    role_name: str = ""
    proposals: List[CastingProposal] = field(default_factory=list)
    chemistry_checks: List[str] = field(default_factory=list)  # 需要安排对手戏验证的组合
    audition_task_summary: str = ""    # 建议的试镜任务摘要
    # 人工确认（最终选角决定 + 理由 + 时间）
    confirmed_actor_name: str = ""
    confirmation_reason: str = ""
    confirmed_at: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class CastingReport:
    """选角报告：所有角色的候选方案"""
    role_count: int = 0
    actor_count: int = 0
    results: List[RoleCastingResult] = field(default_factory=list)
    global_notes: List[str] = field(default_factory=list)  # 全局说明（兼角/档期冲突等）

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self, indent: int = 2, ensure_ascii: bool = False) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=ensure_ascii)

    def get_priority_actors(self, role_name: str) -> List[CastingProposal]:
        """获取某角色值得优先试演的演员"""
        for r in self.results:
            if r.role_name == role_name:
                return [p for p in r.proposals if p.category == "priority_audition"]
        return []

    def get_result_for_role(self, role_name: str) -> Optional[RoleCastingResult]:
        for r in self.results:
            if r.role_name == role_name:
                return r
        return None

    def confirm_actor(self, role_name: str, actor_name: str, reason: str) -> bool:
        """人工确认某角色的最终人选并记录理由。演员名不在候选中则拒绝。"""
        from datetime import datetime
        result = self.get_result_for_role(role_name)
        if result is None:
            return False
        valid_names = [p.actor_name for p in result.proposals]
        if actor_name and actor_name not in valid_names:
            return False
        result.confirmed_actor_name = actor_name
        result.confirmation_reason = reason
        result.confirmed_at = datetime.now().strftime("%Y-%m-%d %H:%M")
        return True

    @classmethod
    def from_dict(cls, data: dict) -> "CastingReport":
        """从项目存档恢复选角报告（递归重建嵌套数据类）。"""
        if not isinstance(data, dict):
            return cls()

        def _str_list(value):
            return [str(x) for x in value if x] if isinstance(value, list) else []

        report = cls(
            role_count=int(data.get("role_count", 0) or 0),
            actor_count=int(data.get("actor_count", 0) or 0),
            global_notes=_str_list(data.get("global_notes")),
        )
        for rd in data.get("results", []) or []:
            if not isinstance(rd, dict):
                continue
            proposals = []
            for pd in rd.get("proposals", []) or []:
                if not isinstance(pd, dict):
                    continue
                comparisons = []
                for ec in pd.get("evidence_comparisons", []) or []:
                    if not isinstance(ec, dict):
                        continue
                    comparisons.append(EvidenceComparison(
                        requirement=ec.get("requirement", "") or "",
                        must_have=bool(ec.get("must_have", False)),
                        actor_evidence=_str_list(ec.get("actor_evidence")),
                        evidence_status=ec.get("evidence_status", "missing") or "missing",
                        notes=ec.get("notes", "") or "",
                    ))
                proposals.append(CastingProposal(
                    actor_name=pd.get("actor_name", "") or "",
                    category=pd.get("category", "needs_more_audition") or "needs_more_audition",
                    supported_requirements=_str_list(pd.get("supported_requirements")),
                    partial_requirements=_str_list(pd.get("partial_requirements")),
                    missing_evidence=_str_list(pd.get("missing_evidence")),
                    explicit_limits=_str_list(pd.get("explicit_limits")),
                    tradeoffs=pd.get("tradeoffs", "") or "",
                    stability_note=pd.get("stability_note", "") or "",
                    adjustment_note=pd.get("adjustment_note", "") or "",
                    next_steps=_str_list(pd.get("next_steps")),
                    reference_score=float(pd.get("reference_score", 0.0) or 0.0),
                    evidence_comparisons=comparisons,
                ))
            report.results.append(RoleCastingResult(
                role_name=rd.get("role_name", "") or "",
                proposals=proposals,
                chemistry_checks=_str_list(rd.get("chemistry_checks")),
                audition_task_summary=rd.get("audition_task_summary", "") or "",
                confirmed_actor_name=rd.get("confirmed_actor_name", "") or "",
                confirmation_reason=rd.get("confirmation_reason", "") or "",
                confirmed_at=rd.get("confirmed_at", "") or "",
            ))
        return report


# ============================================================
# 候选方案 Prompt（v0.5）
# ============================================================

PROPOSAL_SYSTEM_PROMPT = """你是一位选角观察助手，帮助导演整理候选方案，而不是给出单一排名。

你的任务是基于角色的可观察表演要求和演员的观察记录，逐条比较证据，输出候选方案。

【候选分类】
1. priority_audition（值得优先试演）：关键表演要求有直接观察证据支持
2. needs_more_audition（需要补充试镜）：缺乏关键证据，需要补充试镜任务
3. explicit_limit（存在明确限制）：档期冲突、硬性要求不满足等

【证据比较原则】
- 逐条对照角色的可观察表演要求，检查演员的观察记录中是否有对应证据
- 区分：有证据支持（supported）、部分支持（partial）、证据缺失（missing）、有相反证据（contradicted）
- 演员自述"擅长"不等于"已展示能力"，只有实际表演观察才算支持证据
- 特征强度不同不等于不匹配：克制的表演可能恰好适合内敛的角色

【方案取舍说明】
- stability_note：演员当前表现的稳定性（第一遍就完成 vs 需要指导）
- adjustment_note：给调整指令后的改善情况（能执行指导 vs 无变化）
- tradeoffs：与其他候选相比的取舍（谁当前更稳定，谁潜力更大）

【重要规则】
- 不要输出单一总分作为结论，分数只作为参考放在 reference_score
- 材料不足时明确列出缺什么证据、建议什么补充试镜任务
- 单人试镜无法判断"化学反应"，应建议安排对手戏验证
- 输出必须是严格的 JSON 格式
"""

PROPOSAL_USER_PROMPT_TEMPLATE = """请基于以下角色要求和演员观察记录，整理候选方案。

【角色卡（含可观察表演要求）】
---
{role_card_json}
---

【演员观察记录】
---
{actor_profile_json}
---

【数值特征参考（仅反映特征强度差异，不代表演技或匹配度）】
{quantitative_summary}
{settings_section}
请输出候选方案 JSON，结构如下：
{{
  "actor_name": "演员名",
  "category": "priority_audition / needs_more_audition / explicit_limit",
  "supported_requirements": ["有观察证据支持的表演要求"],
  "partial_requirements": ["部分支持的要求"],
  "missing_evidence": ["缺失的关键证据"],
  "explicit_limits": ["明确限制（档期/硬性要求等）"],
  "tradeoffs": "与其他候选相比的取舍说明",
  "stability_note": "当前表现稳定性",
  "adjustment_note": "指导后改善情况",
  "next_steps": ["下一步建议1", "下一步建议2"],
  "reference_score": 0,
  "evidence_comparisons": [
    {{
      "requirement": "角色要求",
      "must_have": true,
      "actor_evidence": ["演员观察证据1", "演员观察证据2"],
      "evidence_status": "supported / partial / missing / contradicted",
      "notes": "说明"
    }}
  ]
}}

请确保：
1. evidence_comparisons 逐条对照角色的 observable_requirements
2. 分类依据要明确：多少关键要求有证据支持、缺什么
3. next_steps 要具体（建议什么试镜任务、给什么调整指令、安排哪组对手戏）
4. reference_score 仅作参考（0-100），不要让它成为主要结论
5. 输出纯 JSON，不要有任何额外文字
"""


# ============================================================
# 匹配引擎（v0.5）
# ============================================================

class MatchingEngine:
    """候选方案引擎：角色卡 × 演员观察记录 → 候选方案报告"""

    def __init__(self, llm_client: Optional[LLMClient] = None):
        self.llm = llm_client or LLMClient()

    def _calculate_quantitative_reference(
        self,
        role_card: RoleCard,
        actor_profile: ActorProfile,
    ) -> tuple:
        """
        计算数值特征参考（降级为辅助参考，不再作为匹配中心）

        Returns:
            (reference_score, summary_lines)
        """
        summaries = []
        similarities = []

        for key, trait_info in QUANTITATIVE_TRAITS.items():
            role_trait = role_card.quantitative_traits.get(key)
            actor_trait = actor_profile.quantitative_traits.get(key)

            role_score = role_trait.score if role_trait else None
            actor_score = actor_trait.score if actor_trait else None

            if role_score is not None and actor_score is not None:
                distance = abs(role_score - actor_score)
                similarity = max(0.0, (10 - distance) / 10.0 * 100.0)
                similarities.append(similarity)
                summaries.append(
                    f"{trait_info['name']}：角色{role_score} vs 演员{actor_score}，"
                    f"特征距离{distance}（注意：这是特征强度差异，不是演技差距）"
                )
            else:
                missing = []
                if role_score is None:
                    missing.append("角色")
                if actor_score is None:
                    missing.append("演员")
                summaries.append(
                    f"{trait_info['name']}：无法判断（{'/'.join(missing)}证据不足）"
                )

        reference_score = sum(similarities) / len(similarities) if similarities else 0.0
        return reference_score, summaries

    def _heuristic_proposal(
        self,
        role_card: RoleCard,
        actor_profile: ActorProfile,
        reference_score: float,
    ) -> CastingProposal:
        """
        启发式候选方案（无 LLM 时基于证据覆盖情况分类）

        逻辑：
        - 统计角色可观察要求中，演员观察记录能支持多少
        - 硬性要求全部支持 → priority_audition
        - 有关键证据缺失 → needs_more_audition
        """
        proposal = CastingProposal(
            actor_name=actor_profile.actor_name,
            reference_score=round(reference_score, 1),
        )

        requirements = role_card.casting_guide.observable_requirements
        if not requirements:
            proposal.category = "needs_more_audition"
            proposal.missing_evidence.append("角色卡缺少可观察表演要求，无法逐条比较")
            proposal.next_steps.append("请先完善角色卡的可观察表演要求")
            return proposal

        # 收集演员所有观察证据文本
        observation_texts = " ".join(
            obs.observed_behavior + " " + obs.possible_interpretation
            for obs in actor_profile.observations
        )

        supported_count = 0
        must_have_missing = 0

        for req in requirements:
            comparison = EvidenceComparison(
                requirement=req.requirement,
                must_have=req.must_have,
            )

            # 优先用可观察信号词匹配（这些是精炼短语，如"停顿""回避目光""语速加快"）
            signal_keywords = list(req.observable_signals)
            # 补充从要求中提取的2-4字短语
            signal_keywords.extend(self._extract_signal_phrases(req.requirement))

            matched_evidence = []
            contradicted_evidence = []
            hit_keywords = set()
            for obs in actor_profile.observations:
                obs_text = obs.observed_behavior + obs.possible_interpretation

                # 先检测相反证据（如要求"克制"但观察到"外放"）
                contrast = self._detect_contradiction(
                    req.requirement + " ".join(req.observable_signals),
                    obs_text,
                )
                if contrast:
                    contradicted_evidence.append(
                        f"[{obs.timestamp}] {obs.observed_behavior}（出现相反信号：{contrast}）"
                    )
                    continue

                for kw in signal_keywords:
                    if len(kw) >= 2 and kw in obs_text:
                        hit_keywords.add(kw)
                        evidence_line = f"[{obs.timestamp}] {obs.observed_behavior}"
                        if evidence_line not in matched_evidence:
                            matched_evidence.append(evidence_line)
                        break

            if contradicted_evidence and matched_evidence:
                comparison.actor_evidence = (contradicted_evidence[:2] + matched_evidence[:2])[:3]
                comparison.evidence_status = "partial"
                comparison.notes = "观察证据相互冲突，既有支持也有相反表现，需指导后复试澄清"
                proposal.missing_evidence.append(
                    f"{req.requirement}（证据冲突，需复试确认）"
                )
                if req.must_have:
                    must_have_missing += 1
            elif contradicted_evidence:
                comparison.actor_evidence = contradicted_evidence[:3]
                comparison.evidence_status = "contradicted"
                comparison.notes = "观察到与要求相反的表现"
                proposal.missing_evidence.append(
                    f"{req.requirement}（现有表现相反，需重新试镜验证）"
                )
                if req.must_have:
                    must_have_missing += 1
            elif matched_evidence:
                comparison.actor_evidence = matched_evidence[:3]
                comparison.evidence_status = "supported"
                comparison.notes = f"匹配信号：{ '、'.join(sorted(hit_keywords)) }"
                proposal.supported_requirements.append(req.requirement)
                supported_count += 1
            else:
                comparison.evidence_status = "missing"
                comparison.notes = "现有观察记录中未找到对应证据"
                proposal.missing_evidence.append(
                    f"{req.requirement}（试镜检查：{req.audition_check}）"
                )
                if req.must_have:
                    must_have_missing += 1

            proposal.evidence_comparisons.append(comparison)

        # 加入演员已有的待验证项
        for vi in actor_profile.verification_items:
            if vi.suggested_task and vi.suggested_task not in proposal.next_steps:
                proposal.next_steps.append(f"补充验证「{vi.item}」：{vi.suggested_task}")

        # 分类逻辑
        total = len(requirements)
        contradicted_count = sum(
            1 for c in proposal.evidence_comparisons if c.evidence_status == "contradicted"
        )

        must_contra = sum(
            1 for c in proposal.evidence_comparisons
            if c.evidence_status == "contradicted" and c.must_have
        )
        nonmust_contra = contradicted_count - must_contra

        if must_contra > 0:
            proposal.category = "needs_more_audition"
            proposal.tradeoffs = (
                f"有{must_contra}项必须满足的要求观察到相反表现，可能是理解偏差，"
                "建议给出明确调整指令后复试，确认演员能否调整表达方式"
            )
            proposal.adjustment_note = "重点检验演员能否在指导后改变表达方式"
            proposal.stability_note = (
                f"{supported_count}/{total}项要求有证据支持，且{must_contra}项硬性要求表现相反"
            )
            proposal.next_steps.insert(0, "针对相反表现项给出调整指令，进行指导后复试")
        elif must_have_missing == 0 and supported_count >= total * 0.6:
            proposal.category = "priority_audition"
            proposal.stability_note = "多数必须满足的表演要求有直接观察证据支持"
            if nonmust_contra > 0:
                proposal.tradeoffs = (
                    f"另有{nonmust_contra}项可排练改善的要求当前表现相反，"
                    "不影响进入试演，但建议在排练中重点引导"
                )
            proposal.next_steps.insert(0, "可安排对手戏验证与其他角色的化学反应")
        else:
            proposal.category = "needs_more_audition"
            proposal.stability_note = f"仅{supported_count}/{total}项要求有证据支持，部分必须项尚待确认"
            proposal.next_steps.insert(0, "需补充试镜以验证缺失的表演要求")

        # 指导后改善情况
        if actor_profile.adjustment_responses:
            effective = sum(
                1 for a in actor_profile.adjustment_responses
                if "有效" in a.change_quality or "调整" in a.change_quality
            )
            proposal.adjustment_note = (
                f"复试中{effective}/{len(actor_profile.adjustment_responses)}次调整有效"
            )

        # 分析状态警告
        if actor_profile.analysis_status == "partial":
            proposal.explicit_limits.append("分析不完整：部分模态处理失败")
        elif actor_profile.analysis_status == "failed":
            proposal.category = "needs_more_audition"
            proposal.explicit_limits.append("分析失败，当前画像不可用，需要重新分析")

        return proposal

    @staticmethod
    def _extract_signal_phrases(text: str) -> List[str]:
        """
        从要求文本提取2-3字核心信号短语（滑动窗口），过滤通用停用词。
        用于在观察记录中做鲁棒的中文关键词匹配。
        """
        import re
        # 通用词停用表：这些词出现在要求里不构成可观察信号
        stopwords = {
            "通过", "表达", "内心", "需要", "演员", "观众", "角色", "理解",
            "情绪", "情感", "表演", "要求", "能够", "可以", "以及", "或者",
            "时候", "场景", "方式", "进行", "具有", "展现", "呈现", "表现",
            "感觉", "状态", "过程", "一个", "这个", "那个", "他们", "我们",
            "自己", "对方", "人物", "戏剧", "演出", "的话", "让其", "使其",
        }
        segments = re.findall(r"[一-鿿]+|[a-zA-Z]+", text)
        phrases = set()
        for seg in segments:
            for n in (2, 3):
                for i in range(len(seg) - n + 1):
                    phrase = seg[i:i + n]
                    # 过滤含停用词或本身是停用词的片段
                    if phrase in stopwords:
                        continue
                    if any(sw in phrase for sw in ("通过", "表达", "需要", "演员", "观众")):
                        continue
                    phrases.add(phrase)
        return list(phrases)

    # 反义信号词对：观察中出现后者时，与前者的要求构成相反证据
    CONTRAST_SIGNALS = {
        "克制": ["外放", "夸张", "丰富", "激烈", "张扬", "大幅度", "砸", "咆哮"],
        "内敛": ["外放", "张扬", "热情", "活跃"],
        "停顿": ["连贯", "不停", "抢话", "抢词", "急促", "没有停顿", "无停顿"],
        "犹豫": ["果断", "坚定", "干脆", "毫不犹豫"],
        "回避目光": ["直视", "注视", "紧盯", "凝视"],
        "直视": ["回避", "躲闪", "避开", "下垂", "低垂", "垂下", "移开", "飘开"],
        "安静": ["喧闹", "吵闹", "活跃"],
        "缓慢": ["急促", "飞快", "匆忙"],
        "低沉": ["高亢", "尖锐", "嘹亮"],
        "平稳": ["加快", "失控", "急促", "提高", "飘忽", "不稳", "颤抖", "崩溃"],
        "平静": ["失控", "激动", "崩溃", "爆发", "尖叫"],
    }

    def _detect_contradiction(self, requirement_text: str, obs_text: str) -> Optional[str]:
        """检测观察文本是否包含与要求相反的信号，返回反义标记（无则 None）。

        额外处理否定语境：如"没有失控""未回避"不应算作相反证据；
        但反义信号本身以"不"开头的（如"不停"）是固定反义，照常命中。
        """
        negatives_prefix = ("没有", "没", "未", "非", "无", "并非")
        for positive, negatives in self.CONTRAST_SIGNALS.items():
            if positive not in requirement_text:
                continue
            for neg in negatives:
                search_from = 0
                while True:
                    idx = obs_text.find(neg, search_from)
                    if idx == -1:
                        break
                    prefix = obs_text[max(0, idx - 2):idx]
                    negated = any(mark in prefix for mark in negatives_prefix)
                    if not neg.startswith("不") and obs_text[max(0, idx - 1):idx] == "不":
                        negated = True
                    if not negated:
                        return neg
                    search_from = idx + len(neg)
        return None

    def match_one(
        self,
        role_card: RoleCard,
        actor_profile: ActorProfile,
        production_settings: Optional[ProductionSettings] = None,
        max_retries: int = 2,
    ) -> Optional[CastingProposal]:
        """单个角色×演员的候选方案（纳入剧团选角设定与档期/兼角约束）"""
        reference_score, quant_summaries = self._calculate_quantitative_reference(
            role_card, actor_profile
        )

        def _finalize(proposal: CastingProposal) -> CastingProposal:
            return self._apply_settings(proposal, production_settings, actor_profile)

        # Mock/演示模式或分析失败时，直接走启发式证据比较（不依赖 LLM 返回格式）
        if self.llm.is_mock_mode or actor_profile.analysis_status == "failed":
            return _finalize(self._heuristic_proposal(role_card, actor_profile, reference_score))

        # 尝试 LLM 分析
        settings_section = self._format_settings_section(
            production_settings, actor_profile
        )
        user_prompt = PROPOSAL_USER_PROMPT_TEMPLATE.format(
            role_card_json=role_card.to_json(),
            actor_profile_json=actor_profile.to_json(),
            quantitative_summary="\n".join(quant_summaries),
            settings_section=settings_section,
        )

        for attempt in range(max_retries + 1):
            result = self.llm.chat_json(PROPOSAL_SYSTEM_PROMPT, user_prompt)

            if "_parse_error" in result:
                if attempt < max_retries:
                    continue
                # LLM 返回无法解析，降级为启发式（服务故障本身会抛 LLMServiceError）
                return _finalize(self._heuristic_proposal(role_card, actor_profile, reference_score))

            try:
                comparisons = []
                for ec in result.get("evidence_comparisons", []):
                    if isinstance(ec, dict):
                        comparisons.append(EvidenceComparison(
                            requirement=ec.get("requirement", ""),
                            must_have=ec.get("must_have", False),
                            actor_evidence=ec.get("actor_evidence", []) if isinstance(ec.get("actor_evidence"), list) else [],
                            evidence_status=ec.get("evidence_status", "missing"),
                            notes=ec.get("notes", ""),
                        ))

                proposal = CastingProposal(
                    actor_name=result.get("actor_name", actor_profile.actor_name),
                    category=result.get("category", "needs_more_audition"),
                    supported_requirements=result.get("supported_requirements", []) if isinstance(result.get("supported_requirements"), list) else [],
                    partial_requirements=result.get("partial_requirements", []) if isinstance(result.get("partial_requirements"), list) else [],
                    missing_evidence=result.get("missing_evidence", []) if isinstance(result.get("missing_evidence"), list) else [],
                    explicit_limits=result.get("explicit_limits", []) if isinstance(result.get("explicit_limits"), list) else [],
                    tradeoffs=result.get("tradeoffs", ""),
                    stability_note=result.get("stability_note", ""),
                    adjustment_note=result.get("adjustment_note", ""),
                    next_steps=result.get("next_steps", []) if isinstance(result.get("next_steps"), list) else [],
                    reference_score=float(result.get("reference_score", reference_score)),
                    evidence_comparisons=comparisons,
                )
                return _finalize(proposal)
            except Exception as e:
                print(f"    候选方案解析失败：{e}")
                if attempt < max_retries:
                    continue
                return _finalize(self._heuristic_proposal(role_card, actor_profile, reference_score))

        return _finalize(self._heuristic_proposal(role_card, actor_profile, reference_score))

    def match_all(
        self,
        role_cards: List[RoleCard],
        actor_profiles: List[ActorProfile],
        production_settings: Optional[ProductionSettings] = None,
    ) -> CastingReport:
        """为所有角色生成候选方案（纳入剧团选角设定）"""
        print(f"\n{'='*60}")
        print(f"  CastingNuwa · 候选方案整理")
        print(f"  角色数：{len(role_cards)} | 演员数：{len(actor_profiles)}")
        print(f"{'='*60}\n")

        report = CastingReport(
            role_count=len(role_cards),
            actor_count=len(actor_profiles),
        )

        for i, role in enumerate(role_cards):
            print(f"  [{i+1}/{len(role_cards)}] 角色：{role.role_name}")
            role_result = RoleCastingResult(role_name=role.role_name)

            for j, actor in enumerate(actor_profiles):
                print(f"    分析演员 {j+1}/{len(actor_profiles)}：{actor.actor_name}...", end=" ")
                proposal = self.match_one(
                    role, actor, production_settings=production_settings
                )
                if proposal:
                    role_result.proposals.append(proposal)
                    category_label = {
                        "priority_audition": "优先试演",
                        "needs_more_audition": "补充试镜",
                        "explicit_limit": "明确限制",
                    }.get(proposal.category, proposal.category)
                    print(f"→ {category_label}（参考分{proposal.reference_score:.0f}）")
                else:
                    print("❌ 失败")

            # 排序：优先试演在前
            category_order = {"priority_audition": 0, "needs_more_audition": 1, "explicit_limit": 2}
            role_result.proposals.sort(
                key=lambda p: category_order.get(p.category, 3)
            )

            # 化学反应检查建议
            priority = [p for p in role_result.proposals if p.category == "priority_audition"]
            if len(priority) >= 2:
                role_result.chemistry_checks.append(
                    f"建议安排 {priority[0].actor_name} 与 {priority[1].actor_name} "
                    f"分别与对手戏演员试演，验证化学反应"
                )

            # 试镜任务摘要
            if role.casting_guide.audition_focus:
                role_result.audition_task_summary = role.casting_guide.audition_focus

            report.results.append(role_result)
            print()

        # 全局分配检查（兼角 / 档期）
        self._append_global_assignment_checks(report, role_cards, production_settings)

        print(f"  候选方案整理完成\n")
        return report

    @staticmethod
    def _format_settings_section(
        settings: Optional[ProductionSettings],
        actor_profile: ActorProfile,
    ) -> str:
        """把剧团设定与演员档期整理进 LLM 提示。"""
        parts = []
        if settings is not None:
            parts.append("【剧团选角设定（纳入限制判断）】")
            parts.append(f"- 是否接受反串：{'是' if settings.allow_cross_gender else '否'}")
            parts.append(f"- 是否接受兼角：{'是' if settings.allow_double_casting else '否'}")
            if settings.performance_style:
                parts.append(f"- 表演风格：{settings.performance_style}")
            if settings.must_have_requirements:
                parts.append("- 必须满足：" + "、".join(settings.must_have_requirements))
            if settings.schedule_constraints:
                parts.append(f"- 档期/排练时间约束：{settings.schedule_constraints}")
        schedule = (getattr(actor_profile, "schedule_info", "") or "").strip()
        if schedule:
            parts.append(f"【该演员自述档期】{schedule}")
            parts.append(
                "若演员档期与剧团排练约束明确冲突，请在 explicit_limits 写明；"
                "无法确定则放入 next_steps 建议人工核对，不要臆断冲突。"
            )
        if not parts:
            return ""
        return "\n" + "\n".join(parts) + "\n"

    @staticmethod
    def _apply_settings(
        proposal: CastingProposal,
        settings: Optional[ProductionSettings],
        actor_profile: ActorProfile,
    ) -> CastingProposal:
        """启发式/LLM 结果统一叠加档期核对提示（自然语言不自动判定冲突）。"""
        if settings is None:
            return proposal
        constraint = (settings.schedule_constraints or "").strip()
        schedule = (getattr(actor_profile, "schedule_info", "") or "").strip()
        if not constraint and not schedule:
            return proposal

        negative_words = ("不能", "无法", "没空", "没有空", "冲突", "不行", "来不了", "没时间")
        if schedule and any(word in schedule for word in negative_words):
            line = (
                f"演员自述档期可能受限：{schedule}；"
                f"剧团排练要求：{constraint or '（未填写）'}，请人工核对"
            )
            if line not in proposal.explicit_limits:
                proposal.explicit_limits.append(line)
        else:
            line = (
                f"请人工核对档期（剧团要求：{constraint or '未填写'}；"
                f"演员自述：{schedule or '未填写'}）"
            )
            if line not in proposal.next_steps:
                proposal.next_steps.append(line)
        return proposal

    def _append_global_assignment_checks(
        self,
        report: CastingReport,
        role_cards: List[RoleCard],
        settings: Optional[ProductionSettings],
    ) -> None:
        """汇总兼角与档期的全局分配提示。"""
        if len(role_cards) > 1 and report.actor_count < report.role_count:
            report.global_notes.append(
                "演员数少于角色数，可能需要兼角安排，请检查兼角可行性和演员档期"
            )

        priority_map: dict = {}
        for result in report.results:
            for proposal in result.proposals:
                if proposal.category == "priority_audition":
                    priority_map.setdefault(proposal.actor_name, []).append(result.role_name)
        double_cast = {
            name: roles for name, roles in priority_map.items() if len(roles) > 1
        }

        disallow_double = settings is not None and not settings.allow_double_casting
        for name, roles in double_cast.items():
            role_text = "、".join(roles)
            if disallow_double:
                report.global_notes.append(
                    f"演员 {name} 同时是角色 {role_text} 的优先试演人选，"
                    "但剧团设定不接受兼角，请为不同角色分配不同演员或安排加试"
                )
            else:
                report.global_notes.append(
                    f"演员 {name} 同时适合角色 {role_text}，"
                    "如安排兼角请确认排练、换装与档期可行"
                )

        if settings is not None and (settings.schedule_constraints or "").strip():
            report.global_notes.append(
                f"剧团排练/档期约束：{settings.schedule_constraints}，请逐位核对演员自述档期"
            )

    @staticmethod
    def save_report(report: CastingReport, output_path: str) -> str:
        """保存选角报告到 JSON 文件"""
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        data = {
            "project": "CastingNuwa · 选角女娲 v0.5",
            "description": "候选方案与证据比较报告（观察记录体系，非单一评分）",
            "role_count": report.role_count,
            "actor_count": report.actor_count,
            "global_notes": report.global_notes,
            "results": [r.to_dict() for r in report.results],
        }
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"  选角报告已保存：{output_path}")
        return output_path

    @staticmethod
    def print_report(report: CastingReport) -> None:
        """打印候选方案报告"""
        print(f"\n{'='*60}")
        print(f"  CastingNuwa · 候选方案报告")
        print(f"  角色：{report.role_count} | 演员：{report.actor_count}")
        print(f"{'='*60}\n")

        for role_result in report.results:
            print(f"{'─'*60}")
            print(f"  角色：{role_result.role_name}")
            print(f"{'─'*60}")

            for p in role_result.proposals:
                category_label = {
                    "priority_audition": "【值得优先试演】",
                    "needs_more_audition": "【需要补充试镜】",
                    "explicit_limit": "【存在明确限制】",
                }.get(p.category, f"【{p.category}】")

                print(f"\n  {p.actor_name} {category_label}（参考分：{p.reference_score:.0f}）")

                if p.supported_requirements:
                    print(f"  ✓ 有证据支持：")
                    for req in p.supported_requirements:
                        print(f"    - {req}")

                if p.missing_evidence:
                    print(f"  ? 缺失证据：")
                    for m in p.missing_evidence:
                        print(f"    - {m}")

                if p.explicit_limits:
                    print(f"  ✗ 明确限制：")
                    for limit in p.explicit_limits:
                        print(f"    - {limit}")

                if p.stability_note:
                    print(f"  稳定性：{p.stability_note}")
                if p.adjustment_note:
                    print(f"  指导后：{p.adjustment_note}")
                if p.tradeoffs:
                    print(f"  方案取舍：{p.tradeoffs}")

                if p.next_steps:
                    print(f"  → 下一步：")
                    for step in p.next_steps:
                        print(f"    - {step}")

            if role_result.chemistry_checks:
                print(f"\n  化学反应验证：")
                for check in role_result.chemistry_checks:
                    print(f"    - {check}")
            print()

        if report.global_notes:
            print(f"【全局说明】")
            for note in report.global_notes:
                print(f"  - {note}")

        print(f"{'='*60}\n")
