"""
CastingNuwa · 选角女娲
演员画像数据模型

v0.5 重构：从"综合评分"改为"观察记录"体系
- 输出观察证据（时间戳+可观察行为），而非笼统评分
- 区分直接观察、推断和无法判断
- 材料不足生成"待验证项"，不硬给中等分
- 自我介绍/过往经历/实际表演证据分别存储
"""

from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict
import json

from .models import TraitScore, QUANTITATIVE_TRAITS


# ============================================================
# 观察记录体系（v0.5 新增）
# ============================================================

@dataclass
class ObservationRecord:
    """
    单条观察记录

    结构：发生了什么 → 可能意味着什么 → 依据是否充分 → 下一轮怎么验证
    这是替代"综合打分"的核心输出格式。
    """
    timestamp: str = ""              # 时间段（如 "0:45-0:52"）
    observed_behavior: str = ""      # 可观察的行为（停顿/动作/语气变化，只描述事实）
    possible_interpretation: str = ""  # 可能意味着什么（结合角色要求提出解释，保留其他解释）
    alternative_interpretations: List[str] = field(default_factory=list)  # 其他可能解释
    evidence_type: str = "直接观察"   # 直接观察 / 推断 / 无法判断
    confidence: str = "中"           # 高 / 中 / 低 / 无法判断
    verification_suggestion: str = ""  # 下一轮怎么验证（建议换什么指令、观察什么变化）
    related_requirement: str = ""    # 对应的角色要求（如"需要通过停顿表达犹豫"）
    source: str = "video"            # 证据来源：video / audio / text / self_report


@dataclass
class VerificationItem:
    """
    待验证项

    材料不足时生成，而不是给中等分。
    回答：缺什么证据、需要补录什么、怎样再试一次。
    """
    item: str = ""                   # 待验证的能力或特质
    why_needed: str = ""             # 为什么需要验证（对应哪个角色要求）
    current_evidence: str = ""       # 目前有什么证据（可能为空或很弱）
    suggested_task: str = ""         # 建议的补充试镜任务
    priority: str = "中"             # 高 / 中 / 低


@dataclass
class EvidenceCollection:
    """
    证据集合（按来源分离存储）

    避免把"说自己擅长"当成"已经展示了能力"。
    """
    performance_evidence: List[ObservationRecord] = field(default_factory=list)  # 实际表演证据
    self_reports: List[str] = field(default_factory=list)  # 自我介绍中的自述（未经表演验证）
    past_experience: List[str] = field(default_factory=list)  # 过往经历描述
    material_gaps: List[str] = field(default_factory=list)  # 材料缺失说明


@dataclass
class AdjustmentResponse:
    """
    指导后复试表现

    两轮试镜的核心：区分"第一次碰巧合适"和"能理解并执行指导"。
    """
    instruction_given: str = ""      # 给出的调整指令
    observed_change: str = ""        # 观察到的变化
    change_quality: str = ""         # 变化是否服务于任务（有效调整/表面调整/无变化/方向错误）
    interpretation: str = ""         # 这说明什么（理解能力/可塑性/执行能力）
    confidence: str = "中"           # 高 / 中 / 低 / 无法判断


@dataclass
class ActorBasicInfo:
    """演员基本信息"""
    name: str = ""                    # 演员姓名/代号
    age_gender: str = ""              # 年龄/性别
    experience: str = ""              # 表演经验描述
    background: str = ""              # 背景信息（专业/爱好等）
    self_description: str = ""        # 自我介绍原文摘要


@dataclass
class VocalTrait:
    """声线特质"""
    pitch: str = ""                   # 音高（高亢/中音/低沉等）
    timbre: str = ""                  # 音色（清亮/沙哑/磁性/温润等）
    clarity: str = ""                 # 清晰度
    pace: str = ""                    # 语速与节奏
    resonance: str = ""               # 共鸣特点
    emotional_expression: str = ""    # 声音中的情感表达能力
    strengths: List[str] = field(default_factory=list)   # 声线优势
    limitations: List[str] = field(default_factory=list) # 声线局限


@dataclass
class FacialExpressiveness:
    """面部表现力"""
    expression_range: str = ""        # 表情幅度（丰富/内敛/木讷等）
    micro_expression: str = ""        # 微表情控制能力
    eye_contact: str = ""             # 眼神传达能力
    facial_symmetry: str = ""         # 面部对称性与协调性
    strengths: List[str] = field(default_factory=list)
    limitations: List[str] = field(default_factory=list)


@dataclass
class PhysicalExpressiveness:
    """肢体表现力"""
    gesture_richness: str = ""        # 手势丰富度
    posture_naturalness: str = ""     # 姿态自然度
    spatial_usage: str = ""           # 空间使用能力
    movement_flow: str = ""           # 移动流畅度
    body_awareness: str = ""          # 身体意识与控制
    strengths: List[str] = field(default_factory=list)
    limitations: List[str] = field(default_factory=list)


@dataclass
class EmotionalRange:
    """情感表达范围"""
    expressible_emotions: List[str] = field(default_factory=list)  # 能表达的情感种类
    emotional_depth: str = ""         # 情感深度（表面/有层次/深刻等）
    transition_fluency: str = ""      # 情感转换流畅度
    strongest_emotions: List[str] = field(default_factory=list)     # 最擅长的情感
    weakest_emotions: List[str] = field(default_factory=list)       # 较弱的情感
    notes: str = ""                    # 备注


@dataclass
class Temperament:
    """气质类型"""
    primary_type: str = ""             # 主要气质类型
    secondary_type: str = ""           # 次要气质类型
    overall_impression: str = ""       # 整体气质印象
    suitable_genres: List[str] = field(default_factory=list)  # 适合的戏剧类型
    unsuitable_genres: List[str] = field(default_factory=list) # 不太适合的类型


@dataclass
class ActingStyle:
    """表演风格与潜力"""
    style_tendency: str = ""           # 表演风格倾向（表现派/体验派/自然主义等）
    naturalness: str = ""              # 表演自然度
    rhythm_sense: str = ""             # 节奏感
    line_delivery: str = ""            # 台词功底
    improvisation: str = ""            # 即兴能力
    learning_ability: str = ""         # 学习能力与可塑性
    experience_level: str = ""         # 经验水平
    potential: str = ""                # 潜力评估
    development_suggestions: List[str] = field(default_factory=list)  # 发展建议


@dataclass
class ActorProfile:
    """
    演员画像 —— 演员画像器的最终输出

    v0.5：从"综合评分"改为"观察记录"体系。
    旧的7维度描述保留作为参考，但核心输出是 observations（观察记录）
    和 verification_items（待验证项），而非一个总分。
    """
    actor_name: str = ""
    basic_info: ActorBasicInfo = field(default_factory=ActorBasicInfo)
    vocal_traits: VocalTrait = field(default_factory=VocalTrait)
    facial_expressiveness: FacialExpressiveness = field(default_factory=FacialExpressiveness)
    physical_expressiveness: PhysicalExpressiveness = field(default_factory=PhysicalExpressiveness)
    emotional_range: EmotionalRange = field(default_factory=EmotionalRange)
    temperament: Temperament = field(default_factory=Temperament)
    acting_style: ActingStyle = field(default_factory=ActingStyle)
    quantitative_traits: Dict[str, TraitScore] = field(default_factory=dict)  # 特征强度参考（非演技评分）

    # v0.5 观察记录体系
    observations: List[ObservationRecord] = field(default_factory=list)  # 观察记录列表
    verification_items: List[VerificationItem] = field(default_factory=list)  # 待验证项
    evidence: EvidenceCollection = field(default_factory=EvidenceCollection)  # 按来源分离的证据
    adjustment_responses: List[AdjustmentResponse] = field(default_factory=list)  # 指导后复试表现

    # 分析来源标记
    analysis_sources: List[str] = field(default_factory=list)  # 如 ["text", "audio", "video"]
    analysis_status: str = "complete"  # complete / partial / failed / demo（区分成功、部分成功、失败、演示）
    analysis_warnings: List[str] = field(default_factory=list)  # 分析过程中的警告（如"视觉分析跳过"）

    # 档期与可用性（演员自述，供兼角/档期冲突检查；不参与演技判断）
    schedule_info: str = ""           # 可排练/可演出时间，如"周三晚、周末全天；周四有课"

    def has_substantive_content(self) -> bool:
        """是否包含可用于选角判断的实质内容。

        仅有名字、其余全空（如模型返回空 JSON）时返回 False，
        用于拒绝“零观察、状态却 complete”的空画像冒充成功。
        """
        if self.observations or self.verification_items or self.adjustment_responses:
            return True
        collection = self.evidence
        if collection is not None and any((
            collection.performance_evidence,
            collection.self_reports,
            collection.past_experience,
        )):
            return True
        for trait in self.quantitative_traits.values():
            if trait is not None and trait.score is not None:
                return True
        return False

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self, indent: int = 2, ensure_ascii: bool = False) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=ensure_ascii)

    @classmethod
    def from_dict(cls, data: dict) -> "ActorProfile":
        """从字典构建演员画像（带容错）"""
        profile = cls()
        profile.actor_name = data.get("actor_name", "")
        profile.analysis_sources = data.get("analysis_sources", [])

        # basic_info
        bi = data.get("basic_info", {})
        if isinstance(bi, dict):
            profile.basic_info = ActorBasicInfo(
                name=bi.get("name", ""),
                age_gender=bi.get("age_gender", ""),
                experience=bi.get("experience", ""),
                background=bi.get("background", ""),
                self_description=bi.get("self_description", ""),
            )

        # vocal_traits
        vt = data.get("vocal_traits", {})
        if isinstance(vt, dict):
            profile.vocal_traits = VocalTrait(
                pitch=vt.get("pitch", ""),
                timbre=vt.get("timbre", ""),
                clarity=vt.get("clarity", ""),
                pace=vt.get("pace", ""),
                resonance=vt.get("resonance", ""),
                emotional_expression=vt.get("emotional_expression", ""),
                strengths=vt.get("strengths", []) if isinstance(vt.get("strengths"), list) else [],
                limitations=vt.get("limitations", []) if isinstance(vt.get("limitations"), list) else [],
            )

        # facial_expressiveness
        fe = data.get("facial_expressiveness", {})
        if isinstance(fe, dict):
            profile.facial_expressiveness = FacialExpressiveness(
                expression_range=fe.get("expression_range", ""),
                micro_expression=fe.get("micro_expression", ""),
                eye_contact=fe.get("eye_contact", ""),
                facial_symmetry=fe.get("facial_symmetry", ""),
                strengths=fe.get("strengths", []) if isinstance(fe.get("strengths"), list) else [],
                limitations=fe.get("limitations", []) if isinstance(fe.get("limitations"), list) else [],
            )

        # physical_expressiveness
        pe = data.get("physical_expressiveness", {})
        if isinstance(pe, dict):
            profile.physical_expressiveness = PhysicalExpressiveness(
                gesture_richness=pe.get("gesture_richness", ""),
                posture_naturalness=pe.get("posture_naturalness", ""),
                spatial_usage=pe.get("spatial_usage", ""),
                movement_flow=pe.get("movement_flow", ""),
                body_awareness=pe.get("body_awareness", ""),
                strengths=pe.get("strengths", []) if isinstance(pe.get("strengths"), list) else [],
                limitations=pe.get("limitations", []) if isinstance(pe.get("limitations"), list) else [],
            )

        # emotional_range
        er = data.get("emotional_range", {})
        if isinstance(er, dict):
            profile.emotional_range = EmotionalRange(
                expressible_emotions=er.get("expressible_emotions", []) if isinstance(er.get("expressible_emotions"), list) else [],
                emotional_depth=er.get("emotional_depth", ""),
                transition_fluency=er.get("transition_fluency", ""),
                strongest_emotions=er.get("strongest_emotions", []) if isinstance(er.get("strongest_emotions"), list) else [],
                weakest_emotions=er.get("weakest_emotions", []) if isinstance(er.get("weakest_emotions"), list) else [],
                notes=er.get("notes", ""),
            )

        # temperament
        tp = data.get("temperament", {})
        if isinstance(tp, dict):
            profile.temperament = Temperament(
                primary_type=tp.get("primary_type", ""),
                secondary_type=tp.get("secondary_type", ""),
                overall_impression=tp.get("overall_impression", ""),
                suitable_genres=tp.get("suitable_genres", []) if isinstance(tp.get("suitable_genres"), list) else [],
                unsuitable_genres=tp.get("unsuitable_genres", []) if isinstance(tp.get("unsuitable_genres"), list) else [],
            )

        # acting_style
        ast = data.get("acting_style", {})
        if isinstance(ast, dict):
            profile.acting_style = ActingStyle(
                style_tendency=ast.get("style_tendency", ""),
                naturalness=ast.get("naturalness", ""),
                rhythm_sense=ast.get("rhythm_sense", ""),
                line_delivery=ast.get("line_delivery", ""),
                improvisation=ast.get("improvisation", ""),
                learning_ability=ast.get("learning_ability", ""),
                experience_level=ast.get("experience_level", ""),
                potential=ast.get("potential", ""),
                development_suggestions=ast.get("development_suggestions", []) if isinstance(ast.get("development_suggestions"), list) else [],
            )

        # quantitative_traits（量化特质评分）
        qt = data.get("quantitative_traits", {})
        if isinstance(qt, dict):
            profile.quantitative_traits = {
                key: TraitScore.from_dict(val)
                for key, val in qt.items()
                if isinstance(val, dict)
            }

        # v0.5 观察记录
        obs = data.get("observations", [])
        if isinstance(obs, list):
            profile.observations = [
                ObservationRecord(
                    timestamp=o.get("timestamp", ""),
                    observed_behavior=o.get("observed_behavior", ""),
                    possible_interpretation=o.get("possible_interpretation", ""),
                    alternative_interpretations=o.get("alternative_interpretations", []) if isinstance(o.get("alternative_interpretations"), list) else [],
                    evidence_type=o.get("evidence_type", "直接观察"),
                    confidence=o.get("confidence", "中"),
                    verification_suggestion=o.get("verification_suggestion", ""),
                    related_requirement=o.get("related_requirement", ""),
                    source=o.get("source", "video"),
                )
                for o in obs if isinstance(o, dict)
            ]

        # 待验证项
        vis = data.get("verification_items", [])
        if isinstance(vis, list):
            profile.verification_items = [
                VerificationItem(
                    item=v.get("item", ""),
                    why_needed=v.get("why_needed", ""),
                    current_evidence=v.get("current_evidence", ""),
                    suggested_task=v.get("suggested_task", ""),
                    priority=v.get("priority", "中"),
                )
                for v in vis if isinstance(v, dict)
            ]

        # 证据集合
        ev = data.get("evidence", {})
        if isinstance(ev, dict):
            profile.evidence = EvidenceCollection(
                performance_evidence=profile.observations,  # 表演证据就是观察记录
                self_reports=ev.get("self_reports", []) if isinstance(ev.get("self_reports"), list) else [],
                past_experience=ev.get("past_experience", []) if isinstance(ev.get("past_experience"), list) else [],
                material_gaps=ev.get("material_gaps", []) if isinstance(ev.get("material_gaps"), list) else [],
            )

        # 复试表现
        ars = data.get("adjustment_responses", [])
        if isinstance(ars, list):
            profile.adjustment_responses = [
                AdjustmentResponse(
                    instruction_given=a.get("instruction_given", ""),
                    observed_change=a.get("observed_change", ""),
                    change_quality=a.get("change_quality", ""),
                    interpretation=a.get("interpretation", ""),
                    confidence=a.get("confidence", "中"),
                )
                for a in ars if isinstance(a, dict)
            ]

        # 分析状态
        profile.analysis_status = data.get("analysis_status", "complete")
        aw = data.get("analysis_warnings", [])
        profile.analysis_warnings = aw if isinstance(aw, list) else []

        # 档期信息
        profile.schedule_info = data.get("schedule_info", "") or ""

        return profile

    def summary(self) -> str:
        """生成人类可读摘要"""
        lines = [
            f"{'='*60}",
            f"  演员画像：{self.actor_name}",
            f"  分析来源：{', '.join(self.analysis_sources) if self.analysis_sources else '文本分析'}",
            f"{'='*60}",
            f"",
            f"【基本信息】",
            f"  年龄/性别：{self.basic_info.age_gender or '未提供'}",
            f"  表演经验：{self.basic_info.experience or '未提供'}",
            f"  背景：{self.basic_info.background or '未提供'}",
            f"",
            f"【声线特质】",
            f"  音高：{self.vocal_traits.pitch or '未分析'} | 音色：{self.vocal_traits.timbre or '未分析'}",
            f"  语速节奏：{self.vocal_traits.pace or '未分析'}",
            f"  情感表达：{self.vocal_traits.emotional_expression or '未分析'}",
            f"  优势：{', '.join(self.vocal_traits.strengths) if self.vocal_traits.strengths else '无'}",
            f"  局限：{', '.join(self.vocal_traits.limitations) if self.vocal_traits.limitations else '无'}",
            f"",
            f"【面部表现力】",
            f"  表情幅度：{self.facial_expressiveness.expression_range or '未分析'}",
            f"  眼神传达：{self.facial_expressiveness.eye_contact or '未分析'}",
            f"  优势：{', '.join(self.facial_expressiveness.strengths) if self.facial_expressiveness.strengths else '无'}",
            f"",
            f"【肢体表现力】",
            f"  手势丰富度：{self.physical_expressiveness.gesture_richness or '未分析'}",
            f"  姿态自然度：{self.physical_expressiveness.posture_naturalness or '未分析'}",
            f"  空间使用：{self.physical_expressiveness.spatial_usage or '未分析'}",
            f"",
            f"【情感表达范围】",
            f"  能表达的情感：{', '.join(self.emotional_range.expressible_emotions) if self.emotional_range.expressible_emotions else '未分析'}",
            f"  情感深度：{self.emotional_range.emotional_depth or '未分析'}",
            f"  最擅长：{', '.join(self.emotional_range.strongest_emotions) if self.emotional_range.strongest_emotions else '无'}",
            f"  较弱：{', '.join(self.emotional_range.weakest_emotions) if self.emotional_range.weakest_emotions else '无'}",
            f"",
            f"【气质类型】",
            f"  主要气质：{self.temperament.primary_type or '未分析'}",
            f"  次要气质：{self.temperament.secondary_type or '未分析'}",
            f"  整体印象：{self.temperament.overall_impression or '未分析'}",
            f"  适合类型：{', '.join(self.temperament.suitable_genres) if self.temperament.suitable_genres else '未分析'}",
            f"",
            f"【表演风格与潜力】",
            f"  风格倾向：{self.acting_style.style_tendency or '未分析'}",
            f"  自然度：{self.acting_style.naturalness or '未分析'}",
            f"  台词功底：{self.acting_style.line_delivery or '未分析'}",
            f"  经验水平：{self.acting_style.experience_level or '未分析'}",
            f"  潜力评估：{self.acting_style.potential or '未分析'}",
            f"  发展建议：",
        ]
        for s in self.acting_style.development_suggestions:
            lines.append(f"    - {s}")

        # 量化特质评分
        if self.quantitative_traits:
            lines.extend([
                f"",
                f"【量化特质评分】",
            ])
            for key, ts in self.quantitative_traits.items():
                trait_name = QUANTITATIVE_TRAITS.get(key, {}).get("name", key)
                score_str = f"{ts.score}/10" if ts.score is not None else "N/A（证据不足）"
                lines.append(f"  {trait_name}：{score_str} | 置信度：{ts.confidence} | 证据：{ts.evidence_count}条")

        lines.append(f"")
        lines.append(f"{'='*60}")
        return "\n".join(lines)
