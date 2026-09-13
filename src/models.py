"""
CastingNuwa · 选角女娲
数据模型定义：角色卡（Role Card）的结构化数据结构

角色卡是"角色蒸馏"的输出，包含 7 个维度 + 量化特质评分：
1. profile        - 基本信息
2. personality    - 性格特质
3. motivation     - 核心动机
4. behavioral_patterns - 行为模式
5. linguistic_dna - 语言 DNA
6. emotional_arc  - 情感弧线
7. casting_guide  - 选角指引
8. quantitative_traits - 量化特质评分（5维度，0-10分+证据+置信度）
"""

from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict
import json


# 量化特质维度定义（角色卡与演员画像共用同一套维度，便于数值匹配）
QUANTITATIVE_TRAITS = {
    "extraversion": {
        "name": "外向性",
        "description": "主动发起对话、表达自我的倾向（0=沉默回避，10=滔滔不绝）",
    },
    "emotional_intensity": {
        "name": "情感张力",
        "description": "情绪的强度与波动幅度（0=平淡，10=剧烈爆发）",
    },
    "rationality": {
        "name": "理性度",
        "description": "以逻辑、论证推进对话的程度（0=纯情绪反应，10=条理清晰）",
    },
    "dominance": {
        "name": "强势度",
        "description": "在对话中占据主导、压制对方的程度（0=完全被动，10=绝对压制）",
    },
    "credibility": {
        "name": "可信度",
        "description": "实际表现出的真诚度与可信度（注意：不是试图辩解的程度，而是读起来是否真诚可信）",
    },
}


@dataclass
class TraitScore:
    """单个量化特质评分"""
    score: Optional[int] = None       # 0-10 分，证据不足时为 None
    evidence_count: int = 0            # 有效证据条数
    evidence: List[str] = field(default_factory=list)  # 依据台词列表
    confidence: str = "无法判断"        # 高 / 中 / 低 / 无法判断

    def to_dict(self) -> dict:
        return {
            "score": self.score,
            "evidence_count": self.evidence_count,
            "evidence": self.evidence,
            "confidence": self.confidence,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "TraitScore":
        if not isinstance(data, dict):
            return cls()
        score = data.get("score")
        # 容错：字符串数字转 int，null/None 保持 None
        if score is not None and not isinstance(score, int):
            try:
                score = int(score)
            except (ValueError, TypeError):
                score = None
        return cls(
            score=score,
            evidence_count=data.get("evidence_count", 0) or 0,
            evidence=data.get("evidence", []) if isinstance(data.get("evidence"), list) else [],
            confidence=data.get("confidence", "无法判断") or "无法判断",
        )


@dataclass
class Profile:
    """基本信息"""
    identity: str = ""              # 剧中身份
    age_gender: str = ""            # 年龄/性别（如剧本有提及）
    scenes_appeared: int = 0        # 出场场景数
    line_count: int = 0             # 台词数量


@dataclass
class PersonalityTrait:
    """单个性格特质"""
    trait: str = ""                  # 特质名称
    evidence: str = ""               # 剧本证据（台词/行为/场景）
    nuance: str = ""                 # 特质的细微差别或矛盾之处


@dataclass
class Motivation:
    """核心动机"""
    want: str = ""                   # 表层欲望（角色自以为想要的）
    need: str = ""                   # 深层需求（角色真正需要的，常与 want 形成张力）
    fear: str = ""                   # 核心恐惧
    trajectory: str = ""             # 动机在剧情中的变化轨迹


@dataclass
class BehavioralPattern:
    """单个行为模式"""
    pattern: str = ""                # 行为模式描述
    context: str = ""                # 触发情境（压力/冲突/日常等）
    example: str = ""                # 剧本中的具体例子


@dataclass
class LinguisticDNA:
    """语言 DNA"""
    vocabulary: str = ""             # 用词偏好（正式/口语/文雅/粗粝等）
    sentence_style: str = ""         # 句式特点（简短/冗长/反问/陈述等）
    catchphrases: List[str] = field(default_factory=list)  # 口头禅或标志性表达
    tone: str = ""                   # 语气特征（嘲讽/温柔/坚定/犹豫等）
    identity_markers: str = ""       # 语言中的身份标记（教育背景/地域/时代）


@dataclass
class TurningPoint:
    """情感弧线转折点"""
    event: str = ""                  # 关键事件
    emotional_change: str = ""       # 情感变化


@dataclass
class EmotionalArc:
    """情感弧线"""
    opening_state: str = ""          # 开场时的情感状态
    turning_points: List[TurningPoint] = field(default_factory=list)  # 关键转折点
    ending_state: str = ""           # 结尾时的情感状态
    arc_type: str = ""               # 整体弧线类型（成长/堕落/救赎/幻灭/循环等）


@dataclass
class CastingGuide:
    """选角指引"""
    actor_type: str = ""             # 适合的演员类型（声线/气质/外形倾向）
    core_requirements: List[str] = field(default_factory=list)  # 核心能力要求
    audition_focus: str = ""         # 试镜时建议考察的重点
    risks: str = ""                  # 选角风险提示
    chemistry_requirements: List[str] = field(default_factory=list)  # 与其他角色的化学反应要求


@dataclass
class RoleCard:
    """
    角色卡 —— 角色蒸馏的最终输出

    这是一个戏剧角色的"认知操作系统"，
    类似于 nuwa-skill 蒸馏出的人物思维 Skill，
    但蒸馏对象是虚构的戏剧角色。
    """
    role_name: str = ""              # 角色名
    profile: Profile = field(default_factory=Profile)
    personality: List[PersonalityTrait] = field(default_factory=list)
    motivation: Motivation = field(default_factory=Motivation)
    behavioral_patterns: List[BehavioralPattern] = field(default_factory=list)
    linguistic_dna: LinguisticDNA = field(default_factory=LinguisticDNA)
    emotional_arc: EmotionalArc = field(default_factory=EmotionalArc)
    casting_guide: CastingGuide = field(default_factory=CastingGuide)
    quantitative_traits: Dict[str, TraitScore] = field(default_factory=dict)  # 量化特质评分

    def to_dict(self) -> dict:
        """转换为字典"""
        return asdict(self)

    def to_json(self, indent: int = 2, ensure_ascii: bool = False) -> str:
        """转换为 JSON 字符串"""
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=ensure_ascii)

    @classmethod
    def from_dict(cls, data: dict) -> "RoleCard":
        """从字典构建角色卡（带容错处理）"""
        card = cls()
        card.role_name = data.get("role_name", "")

        # profile
        p = data.get("profile", {})
        if isinstance(p, dict):
            card.profile = Profile(
                identity=p.get("identity", ""),
                age_gender=p.get("age_gender", ""),
                scenes_appeared=p.get("scenes_appeared", 0),
                line_count=p.get("line_count", 0),
            )

        # personality
        pers = data.get("personality", [])
        if isinstance(pers, list):
            card.personality = [
                PersonalityTrait(
                    trait=item.get("trait", ""),
                    evidence=item.get("evidence", ""),
                    nuance=item.get("nuance", ""),
                )
                for item in pers if isinstance(item, dict)
            ]

        # motivation
        m = data.get("motivation", {})
        if isinstance(m, dict):
            card.motivation = Motivation(
                want=m.get("want", ""),
                need=m.get("need", ""),
                fear=m.get("fear", ""),
                trajectory=m.get("trajectory", ""),
            )

        # behavioral_patterns
        bp = data.get("behavioral_patterns", [])
        if isinstance(bp, list):
            card.behavioral_patterns = [
                BehavioralPattern(
                    pattern=item.get("pattern", ""),
                    context=item.get("context", ""),
                    example=item.get("example", ""),
                )
                for item in bp if isinstance(item, dict)
            ]

        # linguistic_dna
        ld = data.get("linguistic_dna", {})
        if isinstance(ld, dict):
            card.linguistic_dna = LinguisticDNA(
                vocabulary=ld.get("vocabulary", ""),
                sentence_style=ld.get("sentence_style", ""),
                catchphrases=ld.get("catchphrases", []) if isinstance(ld.get("catchphrases"), list) else [],
                tone=ld.get("tone", ""),
                identity_markers=ld.get("identity_markers", ""),
            )

        # emotional_arc
        ea = data.get("emotional_arc", {})
        if isinstance(ea, dict):
            tps = ea.get("turning_points", [])
            card.emotional_arc = EmotionalArc(
                opening_state=ea.get("opening_state", ""),
                turning_points=[
                    TurningPoint(
                        event=tp.get("event", ""),
                        emotional_change=tp.get("emotional_change", ""),
                    )
                    for tp in tps if isinstance(tp, dict)
                ],
                ending_state=ea.get("ending_state", ""),
                arc_type=ea.get("arc_type", ""),
            )

        # casting_guide
        cg = data.get("casting_guide", {})
        if isinstance(cg, dict):
            card.casting_guide = CastingGuide(
                actor_type=cg.get("actor_type", ""),
                core_requirements=cg.get("core_requirements", []) if isinstance(cg.get("core_requirements"), list) else [],
                audition_focus=cg.get("audition_focus", ""),
                risks=cg.get("risks", ""),
                chemistry_requirements=cg.get("chemistry_requirements", []) if isinstance(cg.get("chemistry_requirements"), list) else [],
            )

        # quantitative_traits（量化特质评分）
        qt = data.get("quantitative_traits", {})
        if isinstance(qt, dict):
            card.quantitative_traits = {
                key: TraitScore.from_dict(val)
                for key, val in qt.items()
                if isinstance(val, dict)
            }

        return card

    def summary(self) -> str:
        """生成角色卡的人类可读摘要"""
        lines = [
            f"{'='*60}",
            f"  角色卡：{self.role_name}",
            f"{'='*60}",
            f"",
            f"【基本信息】",
            f"  身份：{self.profile.identity or '未提及'}",
            f"  年龄/性别：{self.profile.age_gender or '未提及'}",
            f"  出场场景：{self.profile.scenes_appeared} | 台词数：{self.profile.line_count}",
            f"",
            f"【性格特质】",
        ]
        for i, t in enumerate(self.personality, 1):
            lines.append(f"  {i}. {t.trait}")
            if t.evidence:
                lines.append(f"     证据：{t.evidence}")
            if t.nuance:
                lines.append(f"     细微差别：{t.nuance}")

        lines.extend([
            f"",
            f"【核心动机】",
            f"  表层欲望（Want）：{self.motivation.want or '未分析'}",
            f"  深层需求（Need）：{self.motivation.need or '未分析'}",
            f"  核心恐惧：{self.motivation.fear or '未分析'}",
            f"  动机变化：{self.motivation.trajectory or '未分析'}",
            f"",
            f"【行为模式】",
        ])
        for i, b in enumerate(self.behavioral_patterns, 1):
            lines.append(f"  {i}. {b.pattern}")
            if b.context:
                lines.append(f"     触发情境：{b.context}")
            if b.example:
                lines.append(f"     例子：{b.example}")

        lines.extend([
            f"",
            f"【语言 DNA】",
            f"  用词偏好：{self.linguistic_dna.vocabulary or '未分析'}",
            f"  句式特点：{self.linguistic_dna.sentence_style or '未分析'}",
            f"  口头禅：{', '.join(self.linguistic_dna.catchphrases) if self.linguistic_dna.catchphrases else '无'}",
            f"  语气：{self.linguistic_dna.tone or '未分析'}",
            f"  身份标记：{self.linguistic_dna.identity_markers or '未分析'}",
            f"",
            f"【情感弧线】",
            f"  开场状态：{self.emotional_arc.opening_state or '未分析'}",
            f"  弧线类型：{self.emotional_arc.arc_type or '未分析'}",
        ])
        for i, tp in enumerate(self.emotional_arc.turning_points, 1):
            lines.append(f"  转折点 {i}：{tp.event} → {tp.emotional_change}")
        lines.append(f"  结尾状态：{self.emotional_arc.ending_state or '未分析'}")

        lines.extend([
            f"",
            f"【选角指引】",
            f"  适合演员类型：{self.casting_guide.actor_type or '未分析'}",
            f"  核心能力要求：",
        ])
        for req in self.casting_guide.core_requirements:
            lines.append(f"    - {req}")
        lines.extend([
            f"  试镜重点：{self.casting_guide.audition_focus or '未分析'}",
            f"  选角风险：{self.casting_guide.risks or '未分析'}",
            f"  化学反应要求：",
        ])
        for chem in self.casting_guide.chemistry_requirements:
            lines.append(f"    - {chem}")

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
