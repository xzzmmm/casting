"""
CastingNuwa · 选角女娲
演员画像数据模型

演员画像是"演员画像器"的输出，包含 7 个维度 + 量化特质评分：
1. basic_info       - 基本信息
2. vocal_traits     - 声线特质
3. facial_expressiveness - 面部表现力
4. physical_expressiveness - 肢体表现力
5. emotional_range  - 情感表达范围
6. temperament      - 气质类型
7. acting_style     - 表演风格与潜力
8. quantitative_traits - 量化特质评分（与角色卡共用5维度，便于数值匹配）
"""

from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict
import json

from .models import TraitScore, QUANTITATIVE_TRAITS


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

    对演员的多维度综合分析，用于与角色卡做匹配。
    当前版本主要基于文本输入（自我介绍+试镜转写）分析，
    视频/音频分析为可扩展接口。
    """
    actor_name: str = ""
    basic_info: ActorBasicInfo = field(default_factory=ActorBasicInfo)
    vocal_traits: VocalTrait = field(default_factory=VocalTrait)
    facial_expressiveness: FacialExpressiveness = field(default_factory=FacialExpressiveness)
    physical_expressiveness: PhysicalExpressiveness = field(default_factory=PhysicalExpressiveness)
    emotional_range: EmotionalRange = field(default_factory=EmotionalRange)
    temperament: Temperament = field(default_factory=Temperament)
    acting_style: ActingStyle = field(default_factory=ActingStyle)
    quantitative_traits: Dict[str, TraitScore] = field(default_factory=dict)  # 量化特质评分（与角色卡共用维度）

    # 分析来源标记
    analysis_sources: List[str] = field(default_factory=list)  # 如 ["text", "audio", "video"]

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
