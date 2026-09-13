"""
CastingNuwa · 选角女娲
匹配引擎（Matching Engine）

将角色卡与演员画像进行多维度匹配，
输出匹配度评分、匹配理由、风险提示和试镜建议。

匹配逻辑：
1. 硬性匹配（Hard Match）：性别、年龄范围、特殊技能等硬性要求
2. 数值匹配（Quantitative Match）：5维度量化特质的分值距离计算
3. 软性匹配（Soft Match）：6维度语义匹配 + LLM 推理
4. 综合评分：数值分(30%) + 文本分(70%) 加权融合，0-100 分
"""

import os
import json
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict, Any

from .models import RoleCard, QUANTITATIVE_TRAITS
from .actor_models import ActorProfile
from .llm_client import LLMClient


# ============================================================
# 匹配结果数据模型
# ============================================================

@dataclass
class DimensionScore:
    """单个维度的匹配评分"""
    dimension: str = ""               # 维度名称
    score: float = 0.0                # 评分 0-100
    reason: str = ""                  # 匹配理由
    risk: str = ""                    # 风险提示


@dataclass
class QuantitativeDimensionMatch:
    """单个量化维度的数值匹配详情"""
    dimension_key: str = ""           # 维度键（如 extraversion）
    dimension_name: str = ""          # 维度中文名
    role_score: Optional[int] = None  # 角色分值
    actor_score: Optional[int] = None # 演员分值
    distance: Optional[int] = None    # 分值距离
    similarity: float = 0.0           # 相似度 0-100
    included: bool = False            # 是否计入总分（双方都有分值才计入）


@dataclass
class MatchResult:
    """单个角色×演员的匹配结果"""
    role_name: str = ""
    actor_name: str = ""
    overall_score: float = 0.0        # 综合匹配度 0-100（数值分30% + 文本分70%）
    match_level: str = ""              # 匹配等级（高度匹配/较为匹配/一般匹配/不太匹配）
    dimension_scores: List[DimensionScore] = field(default_factory=list)
    match_reasons: List[str] = field(default_factory=list)   # 匹配理由
    risks: List[str] = field(default_factory=list)            # 风险提示
    audition_suggestions: List[str] = field(default_factory=list)  # 试镜建议
    summary: str = ""                 # 综合评价
    # 数值匹配层
    quantitative_score: float = 0.0   # 数值匹配分 0-100（基于5维度量化特质的分值距离）
    text_score: float = 0.0           # 文本匹配分 0-100（LLM 语义匹配）
    quantitative_matches: List[QuantitativeDimensionMatch] = field(default_factory=list)  # 各量化维度匹配详情
    quantitative_weight: float = 0.3  # 数值匹配权重
    text_weight: float = 0.7          # 文本匹配权重

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class CastingReport:
    """选角报告：所有角色×演员的匹配结果"""
    role_count: int = 0
    actor_count: int = 0
    results: List[MatchResult] = field(default_factory=list)
    recommendations: Dict[str, str] = field(default_factory=dict)  # 每个角色的推荐演员

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self, indent: int = 2, ensure_ascii: bool = False) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=ensure_ascii)

    def get_best_actor_for_role(self, role_name: str) -> Optional[MatchResult]:
        """获取某个角色的最佳匹配演员"""
        role_results = [r for r in self.results if r.role_name == role_name]
        if not role_results:
            return None
        return max(role_results, key=lambda x: x.overall_score)

    def get_roles_for_actor(self, actor_name: str) -> List[MatchResult]:
        """获取某个演员适合的所有角色（按匹配度排序）"""
        actor_results = [r for r in self.results if r.actor_name == actor_name]
        return sorted(actor_results, key=lambda x: x.overall_score, reverse=True)


# ============================================================
# 匹配 Prompt
# ============================================================

MATCH_SYSTEM_PROMPT = """你是一位资深选角导演，擅长将演员与戏剧角色进行精准匹配。
你的任务是根据角色卡（角色的认知操作系统）和演员画像（演员的多维度特质），
进行多维度匹配分析，给出可解释的匹配建议。

匹配分析维度：
1. 性格与气质匹配：角色性格特质 vs 演员气质类型
2. 动机与情感深度匹配：角色的情感弧线 vs 演员的情感表达范围
3. 语言与台词匹配：角色的语言DNA vs 演员的声线特质和台词功底
4. 行为与肢体匹配：角色的行为模式 vs 演员的肢体表现力
5. 表演风格匹配：角色需要的表演风格 vs 演员的表演风格倾向
6. 潜力与可塑性：角色的难度 vs 演员的经验水平和学习能力

【评分标准】
- 90-100：高度匹配，演员几乎是为这个角色而生
- 75-89：较为匹配，演员很适合这个角色，少量方面需要调整
- 60-74：一般匹配，演员可以胜任但需要较多训练和指导
- 40-59：不太匹配，演员与角色有明显差距，不建议选角
- 0-39：完全不匹配

【重要规则】
- 评分要客观，基于角色卡和演员画像的具体内容
- 每个维度的评分都要有具体理由
- 既要指出匹配的优势，也要指出风险和不足
- 试镜建议要具体可操作，建议考察特定的场景或台词
- 输出必须是严格的 JSON 格式
"""

MATCH_USER_PROMPT_TEMPLATE = """请对以下角色和演员进行匹配分析。

【角色卡】
---
{role_card_json}
---

【演员画像】
---
{actor_profile_json}
---

【数值匹配参考（基于5维度量化特质的分值距离计算）】
综合数值匹配分：{quantitative_score}/100
各维度详情：
{quantitative_summary}

【说明】
- 以上数值匹配分是基于角色卡和演员画像的量化特质评分（外向性/情感张力/理性度/强势度/可信度）自动计算的
- 请将数值匹配分作为参考，结合你对角色卡和演员画像的深度语义分析，给出最终的文本匹配分
- 如果数值匹配分与你的语义判断有较大差异，请在匹配理由中说明原因
- 你输出的 overall_score 将作为文本匹配分，最终综合分 = 数值分×30% + 文本分×70%

请输出匹配分析 JSON，结构如下：
{{
  "role_name": "角色名",
  "actor_name": "演员名",
  "overall_score": 0,
  "match_level": "高度匹配/较为匹配/一般匹配/不太匹配",
  "dimension_scores": [
    {{
      "dimension": "性格与气质匹配",
      "score": 0,
      "reason": "",
      "risk": ""
    }},
    {{
      "dimension": "动机与情感深度匹配",
      "score": 0,
      "reason": "",
      "risk": ""
    }},
    {{
      "dimension": "语言与台词匹配",
      "score": 0,
      "reason": "",
      "risk": ""
    }},
    {{
      "dimension": "行为与肢体匹配",
      "score": 0,
      "reason": "",
      "risk": ""
    }},
    {{
      "dimension": "表演风格匹配",
      "score": 0,
      "reason": "",
      "risk": ""
    }},
    {{
      "dimension": "潜力与可塑性",
      "score": 0,
      "reason": "",
      "risk": ""
    }}
  ],
  "match_reasons": ["理由1", "理由2"],
  "risks": ["风险1", "风险2"],
  "audition_suggestions": ["建议1", "建议2"],
  "summary": "综合评价（2-3句话）"
}}

输出纯 JSON，不要有任何额外文字。
"""


# ============================================================
# 匹配引擎
# ============================================================

class MatchingEngine:
    """匹配引擎：角色卡 × 演员画像 → 选角报告"""

    def __init__(
        self,
        llm_client: Optional[LLMClient] = None,
        quantitative_weight: float = 0.3,
        text_weight: float = 0.7,
    ):
        """
        Args:
            llm_client: LLM 客户端
            quantitative_weight: 数值匹配权重（默认0.3）
            text_weight: 文本匹配权重（默认0.7）
        """
        self.llm = llm_client or LLMClient()
        self.quantitative_weight = quantitative_weight
        self.text_weight = text_weight

    def _calculate_quantitative_match(
        self,
        role_card: RoleCard,
        actor_profile: ActorProfile,
    ) -> tuple:
        """
        计算数值匹配分（基于5维度量化特质的分值距离）

        Returns:
            (quantitative_score, quantitative_matches)
            - quantitative_score: 0-100 分
            - quantitative_matches: 各维度匹配详情列表
        """
        matches = []
        similarities = []

        for key, trait_info in QUANTITATIVE_TRAITS.items():
            role_trait = role_card.quantitative_traits.get(key)
            actor_trait = actor_profile.quantitative_traits.get(key)

            role_score = role_trait.score if role_trait else None
            actor_score = actor_trait.score if actor_trait else None

            dm = QuantitativeDimensionMatch(
                dimension_key=key,
                dimension_name=trait_info.get("name", key),
                role_score=role_score,
                actor_score=actor_score,
            )

            # 双方都有有效分值才计入
            if role_score is not None and actor_score is not None:
                distance = abs(role_score - actor_score)
                similarity = max(0.0, (10 - distance) / 10.0 * 100.0)
                dm.distance = distance
                dm.similarity = similarity
                dm.included = True
                similarities.append(similarity)
            else:
                dm.included = False

            matches.append(dm)

        # 计算平均分（只计入双方都有分值的维度）
        if similarities:
            quantitative_score = sum(similarities) / len(similarities)
        else:
            quantitative_score = 0.0  # 没有任何有效维度时为0，完全依赖文本匹配

        return quantitative_score, matches

    def match_one(
        self,
        role_card: RoleCard,
        actor_profile: ActorProfile,
        max_retries: int = 2,
    ) -> Optional[MatchResult]:
        """
        匹配单个角色和演员

        Args:
            role_card: 角色卡
            actor_profile: 演员画像
            max_retries: 最大重试次数

        Returns:
            匹配结果
        """
        # Step 1: 计算数值匹配分（基于5维度量化特质的分值距离）
        quantitative_score, quant_matches = self._calculate_quantitative_match(
            role_card, actor_profile
        )

        # 构建数值匹配参考摘要，传给 LLM 作为辅助参考
        quant_summary_parts = []
        for qm in quant_matches:
            if qm.included:
                quant_summary_parts.append(
                    f"{qm.dimension_name}：角色{qm.role_score}分 vs 演员{qm.actor_score}分，"
                    f"距离{qm.distance}，相似度{qm.similarity:.0f}%"
                )
            else:
                missing = []
                if qm.role_score is None:
                    missing.append("角色")
                if qm.actor_score is None:
                    missing.append("演员")
                quant_summary_parts.append(
                    f"{qm.dimension_name}：无法判断（{'/'.join(missing)}分值缺失）"
                )
        quant_summary = "\n".join(quant_summary_parts) if quant_summary_parts else "无量化特质数据"

        user_prompt = MATCH_USER_PROMPT_TEMPLATE.format(
            role_card_json=role_card.to_json(),
            actor_profile_json=actor_profile.to_json(),
            quantitative_summary=quant_summary,
            quantitative_score=f"{quantitative_score:.1f}",
        )

        for attempt in range(max_retries + 1):
            if attempt > 0:
                print(f"    [重试 {attempt}/{max_retries}]...")

            result = self.llm.chat_json(MATCH_SYSTEM_PROMPT, user_prompt)

            if "_parse_error" in result:
                if attempt < max_retries:
                    continue
                return None

            try:
                text_score = float(result.get("overall_score", 0))

                # 融合数值分和文本分
                # 如果没有任何有效量化维度，数值权重降为0，完全依赖文本分
                effective_quant_weight = self.quantitative_weight if any(
                    qm.included for qm in quant_matches
                ) else 0.0
                effective_text_weight = 1.0 - effective_quant_weight

                overall_score = (
                    quantitative_score * effective_quant_weight
                    + text_score * effective_text_weight
                )

                match = MatchResult(
                    role_name=result.get("role_name", role_card.role_name),
                    actor_name=result.get("actor_name", actor_profile.actor_name),
                    overall_score=round(overall_score, 1),
                    match_level=result.get("match_level", ""),
                    dimension_scores=[
                        DimensionScore(
                            dimension=ds.get("dimension", ""),
                            score=float(ds.get("score", 0)),
                            reason=ds.get("reason", ""),
                            risk=ds.get("risk", ""),
                        )
                        for ds in result.get("dimension_scores", [])
                        if isinstance(ds, dict)
                    ],
                    match_reasons=result.get("match_reasons", []),
                    risks=result.get("risks", []),
                    audition_suggestions=result.get("audition_suggestions", []),
                    summary=result.get("summary", ""),
                    quantitative_score=round(quantitative_score, 1),
                    text_score=round(text_score, 1),
                    quantitative_matches=quant_matches,
                    quantitative_weight=effective_quant_weight,
                    text_weight=effective_text_weight,
                )
                return match
            except Exception as e:
                print(f"    匹配结果解析失败：{e}")
                if attempt < max_retries:
                    continue
                return None

        return None

    def match_all(
        self,
        role_cards: List[RoleCard],
        actor_profiles: List[ActorProfile],
    ) -> CastingReport:
        """
        匹配所有角色和演员（笛卡尔积）

        Args:
            role_cards: 角色卡列表
            actor_profiles: 演员画像列表

        Returns:
            选角报告
        """
        print(f"\n{'='*60}")
        print(f"  CastingNuwa · 匹配引擎")
        print(f"  角色数：{len(role_cards)} | 演员数：{len(actor_profiles)}")
        print(f"  匹配组合：{len(role_cards) * len(actor_profiles)}")
        print(f"{'='*60}\n")

        report = CastingReport(
            role_count=len(role_cards),
            actor_count=len(actor_profiles),
        )

        for i, role in enumerate(role_cards):
            print(f"  [{i+1}/{len(role_cards)}] 角色：{role.role_name}")

            best_score = -1
            best_actor = ""

            for j, actor in enumerate(actor_profiles):
                print(f"    匹配演员 {j+1}/{len(actor_profiles)}：{actor.actor_name}...", end=" ")

                match = self.match_one(role, actor)
                if match:
                    report.results.append(match)
                    print(f"✅ {match.overall_score:.0f}分 ({match.match_level})")

                    if match.overall_score > best_score:
                        best_score = match.overall_score
                        best_actor = actor.actor_name
                else:
                    print("❌ 失败")

            if best_actor:
                report.recommendations[role.role_name] = best_actor
                print(f"    → 推荐：{best_actor} ({best_score:.0f}分)")
            print()

        print(f"  匹配完成：共 {len(report.results)} 个匹配结果\n")
        return report

    @staticmethod
    def save_report(report: CastingReport, output_path: str) -> str:
        """保存选角报告到 JSON 文件"""
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

        data = {
            "project": "CastingNuwa · 选角女娲",
            "description": "AI 选角匹配报告",
            "role_count": report.role_count,
            "actor_count": report.actor_count,
            "recommendations": report.recommendations,
            "results": [r.to_dict() for r in report.results],
        }

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        print(f"  💾 选角报告已保存：{output_path}")
        return output_path

    @staticmethod
    def print_report(report: CastingReport) -> None:
        """打印选角报告的人类可读摘要"""
        print(f"\n{'='*60}")
        print(f"  CastingNuwa · 选角报告")
        print(f"  角色：{report.role_count} | 演员：{report.actor_count} | 匹配：{len(report.results)}")
        print(f"{'='*60}\n")

        # 推荐汇总
        print(f"【推荐汇总】")
        for role_name, actor_name in report.recommendations.items():
            best = report.get_best_actor_for_role(role_name)
            if best:
                print(f"  {role_name} → {actor_name}（{best.overall_score:.0f}分，{best.match_level}）")
        print()

        # 详细结果
        for role_name in report.recommendations.keys():
            role_results = sorted(
                [r for r in report.results if r.role_name == role_name],
                key=lambda x: x.overall_score,
                reverse=True,
            )

            print(f"{'─'*60}")
            print(f"  角色：{role_name}")
            print(f"{'─'*60}")

            for r in role_results:
                print(f"\n  演员：{r.actor_name} | 匹配度：{r.overall_score:.0f}分 | {r.match_level}")
                print(f"  综合评价：{r.summary}")

                if r.match_reasons:
                    print(f"  ✓ 匹配优势：")
                    for reason in r.match_reasons:
                        print(f"    - {reason}")

                if r.risks:
                    print(f"  ⚠ 风险提示：")
                    for risk in r.risks:
                        print(f"    - {risk}")

                if r.audition_suggestions:
                    print(f"  🎬 试镜建议：")
                    for sug in r.audition_suggestions:
                        print(f"    - {sug}")

                # 分维度评分
                if r.dimension_scores:
                    print(f"  📊 分维度评分：")
                    for ds in r.dimension_scores:
                        bar = "█" * int(ds.score / 10) + "░" * (10 - int(ds.score / 10))
                        print(f"    {ds.dimension:<20} {bar} {ds.score:.0f}分")

            print()

        print(f"{'='*60}\n")
