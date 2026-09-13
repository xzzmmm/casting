"""
CastingNuwa · 选角女娲
多模态融合分析器（Multimodal Analyzer）

功能：
1. 融合文本（自我介绍/试镜转写）、音频（声学特征）、视觉（面部表情/肢体语言）特征
2. 将多模态特征转化为自然语言描述
3. 调用 LLM 进行综合分析，生成更全面、更准确的演员画像
4. 支持单模态/双模态/三模态输入

输出：
- 多模态演员画像（ActorProfile）
- 多模态分析报告
"""

import os
import json
from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Any

from .actor_models import ActorProfile
from .audio_processor import AudioAnalysisResult, AcousticFeatures
from .vision_processor import VisionAnalysisResult, FacialExpressionFeatures, BodyLanguageFeatures
from .llm_client import LLMClient


# ============================================================
# 多模态 Prompt
# ============================================================

MULTIMODAL_SYSTEM_PROMPT = """你是一位资深选角导演与表演指导，拥有二十年演员评估与选角经验。
你擅长综合演员的文本材料、声音表现和视觉表现，进行全面、客观的多维度评估。

你的评估严格遵循演员画像的 7 个维度：
1. 基本信息
2. 声线特质（音高、音色、清晰度、语速节奏、共鸣、情感表达、优势/局限）
3. 面部表现力（表情幅度、微表情控制、眼神传达、优势/局限）
4. 肢体表现力（手势丰富度、姿态自然度、空间使用、移动流畅度、优势/局限）
5. 情感表达范围（能表达的情感种类、情感深度、转换流畅度、最擅长/较弱）
6. 气质类型（主要/次要气质、整体印象、适合/不适合的戏剧类型）
7. 表演风格与潜力（风格倾向、自然度、节奏感、台词功底、即兴能力、学习能力、经验水平、潜力、发展建议）

【重要规则】
- 综合所有可用的模态信息（文本/音频/视觉），不要只依赖单一模态
- 声学特征和视觉特征是客观数据，文本材料是主观描述，两者要相互印证和补充
- 如果某个模态的信息缺失，明确标注"该维度基于XX模态分析"，不要编造
- 评估要客观、具体，避免泛泛而谈
- 优势和局限要平衡，既要肯定也要指出不足
- 潜力评估要考虑演员的经验水平、学习能力和多模态表现的一致性
- 输出必须是严格的 JSON 格式
"""

MULTIMODAL_USER_PROMPT_TEMPLATE = """请对以下演员进行多模态综合画像分析。

【演员基本信息】
{basic_info}

【文本材料】（自我介绍/试镜转写）
---
{text_material}
---

【音频分析结果】（基于试镜音频/视频的声学特征分析）
---
{audio_analysis}
---

【视觉分析结果】（基于试镜视频的面部表情和肢体语言分析）
---
{vision_analysis}
---

【可用模态】{available_modalities}

请综合以上所有信息，输出该演员的完整画像 JSON，结构如下：
{{
  "actor_name": "演员姓名",
  "analysis_sources": ["text", "audio", "video"],
  "basic_info": {{
    "name": "",
    "age_gender": "",
    "experience": "",
    "background": "",
    "self_description": ""
  }},
  "vocal_traits": {{
    "pitch": "",
    "timbre": "",
    "clarity": "",
    "pace": "",
    "resonance": "",
    "emotional_expression": "",
    "strengths": [],
    "limitations": []
  }},
  "facial_expressiveness": {{
    "expression_range": "",
    "micro_expression": "",
    "eye_contact": "",
    "facial_symmetry": "",
    "strengths": [],
    "limitations": []
  }},
  "physical_expressiveness": {{
    "gesture_richness": "",
    "posture_naturalness": "",
    "spatial_usage": "",
    "movement_flow": "",
    "body_awareness": "",
    "strengths": [],
    "limitations": []
  }},
  "emotional_range": {{
    "expressible_emotions": [],
    "emotional_depth": "",
    "transition_fluency": "",
    "strongest_emotions": [],
    "weakest_emotions": [],
    "notes": ""
  }},
  "temperament": {{
    "primary_type": "",
    "secondary_type": "",
    "overall_impression": "",
    "suitable_genres": [],
    "unsuitable_genres": []
  }},
  "acting_style": {{
    "style_tendency": "",
    "naturalness": "",
    "rhythm_sense": "",
    "line_delivery": "",
    "improvisation": "",
    "learning_ability": "",
    "experience_level": "",
    "potential": "",
    "development_suggestions": []
  }}
}}

输出纯 JSON，不要有任何额外文字。
"""


@dataclass
class MultimodalAnalysisResult:
    """多模态分析结果"""
    actor_profile: ActorProfile = field(default_factory=ActorProfile)
    modalities_used: List[str] = field(default_factory=list)
    audio_features: Optional[AcousticFeatures] = None
    facial_features: Optional[FacialExpressionFeatures] = None
    body_features: Optional[BodyLanguageFeatures] = None
    analysis_report: str = ""

    def to_dict(self) -> dict:
        return {
            "actor_profile": self.actor_profile.to_dict(),
            "modalities_used": self.modalities_used,
            "audio_features": self.audio_features.to_dict() if self.audio_features else None,
            "facial_features": self.facial_features.to_dict() if self.facial_features else None,
            "body_features": self.body_features.to_dict() if self.body_features else None,
            "analysis_report": self.analysis_report,
        }


class MultimodalAnalyzer:
    """多模态融合分析器"""

    def __init__(self, llm_client: Optional[LLMClient] = None):
        self.llm = llm_client or LLMClient()

    def _format_audio_analysis(self, audio_result: Optional[AudioAnalysisResult]) -> str:
        """将音频分析结果格式化为自然语言"""
        if audio_result is None:
            return "无音频分析数据（未提供音频/视频材料）"

        f = audio_result.acoustic_features
        lines = [
            f"音频时长：{f.duration:.1f}秒",
            f"转写文本字数：{audio_result.word_count}字",
            f"",
            f"【音高特征】",
            f"  平均音高：{f.pitch_mean:.1f}Hz | 范围：{f.pitch_min:.0f}-{f.pitch_max:.0f}Hz",
            f"  分类：{f.pitch_category}",
            f"",
            f"【能量/响度】",
            f"  平均RMS：{f.rms_mean:.4f} | 最大：{f.rms_max:.4f}",
            f"",
            f"【语速/节奏】",
            f"  语速：{f.speech_rate:.0f}字/分钟 | 分类：{f.pace_category}",
            f"  停顿：{f.pause_count}次",
            f"",
            f"【音色】",
            f"  频谱质心：{f.spectral_centroid_mean:.0f}Hz | 分类：{f.timbre_category}",
            f"",
            f"【韵律/情感】",
            f"  F0变化量：{f.f0_variation:.3f} | 能量变化：{f.energy_variation:.4f}",
            f"  情感表达评估：{f.emotion_expression}",
            f"",
            f"【声线优势】{', '.join(f.vocal_strengths) if f.vocal_strengths else '无'}",
            f"【声线局限】{', '.join(f.vocal_limitations) if f.vocal_limitations else '无'}",
        ]
        return "\n".join(lines)

    def _format_vision_analysis(self, vision_result: Optional[VisionAnalysisResult]) -> str:
        """将视觉分析结果格式化为自然语言"""
        if vision_result is None:
            return "无视觉分析数据（未提供视频材料）"

        f = vision_result.facial_features
        b = vision_result.body_features

        lines = [
            f"分析帧数：{vision_result.frames_extracted}",
            f"",
            f"【面部表情】",
            f"  人脸检测率：{f.face_detected_ratio:.1%}",
            f"  笑容：平均幅度{f.smile_intensity_mean:.3f} | 笑容帧比例{f.smile_ratio:.1%} | 最大{f.max_smile_intensity:.3f}",
            f"  眼睛：平均开合度{f.eye_openness_mean:.3f} | 眨眼频率{f.blink_rate:.1f}次/分钟",
            f"  眉毛：抬升度{f.brow_raise_mean:.3f} | 皱眉度{f.brow_furrow_mean:.3f}",
            f"  表情丰富度：变化范围{f.expression_range:.3f} | 变化量{f.expression_variation:.3f}",
            f"  微表情估计：{f.micro_expression_count}次",
            f"  表情分类：{f.expression_category}",
            f"  眼神传达：{f.eye_contact_category}",
            f"  面部优势：{', '.join(f.facial_strengths) if f.facial_strengths else '无'}",
            f"  面部局限：{', '.join(f.facial_limitations) if f.facial_limitations else '无'}",
            f"",
            f"【肢体语言】",
            f"  姿态检测率：{b.pose_detected_ratio:.1%}",
            f"  手势：平均移动幅度{b.hand_movement_mean:.3f} | 手势帧比例{b.gesture_ratio:.1%} | 手臂伸展度{b.arm_extension_mean:.3f}",
            f"  姿态：挺拔度{b.posture_straightness:.3f} | 变化量{b.posture_variation:.3f}",
            f"  头部：移动幅度{b.head_movement_mean:.3f} | 倾斜度{b.head_tilt_mean:.3f}",
            f"  空间使用：水平范围{b.spatial_usage_width:.3f} | 深度范围{b.spatial_usage_depth:.3f}",
            f"  移动流畅度：{b.movement_flow:.3f}",
            f"  手势分类：{b.gesture_category}",
            f"  姿态分类：{b.posture_category}",
            f"  空间分类：{b.spatial_category}",
            f"  肢体优势：{', '.join(b.body_strengths) if b.body_strengths else '无'}",
            f"  肢体局限：{', '.join(b.body_limitations) if b.body_limitations else '无'}",
        ]
        return "\n".join(lines)

    def analyze(
        self,
        actor_name: str = "",
        text_material: str = "",
        audio_result: Optional[AudioAnalysisResult] = None,
        vision_result: Optional[VisionAnalysisResult] = None,
        basic_info: str = "",
        max_retries: int = 2,
    ) -> MultimodalAnalysisResult:
        """
        多模态综合分析

        Args:
            actor_name: 演员姓名
            text_material: 文本材料（自我介绍/试镜转写）
            audio_result: 音频分析结果
            vision_result: 视觉分析结果
            basic_info: 基本信息描述
            max_retries: 最大重试次数

        Returns:
            多模态分析结果
        """
        # 确定可用模态
        modalities = []
        if text_material:
            modalities.append("text")
        if audio_result:
            modalities.append("audio")
        if vision_result:
            modalities.append("video")

        print(f"\n{'='*60}")
        print(f"  CastingNuwa · 多模态融合分析")
        print(f"  演员：{actor_name or '未命名'}")
        print(f"  可用模态：{', '.join(modalities) if modalities else '无'}")
        print(f"{'='*60}\n")

        if self.llm.is_mock_mode:
            print(f"  ⚠️  当前为 Mock 演示模式")

        # 格式化各模态信息
        audio_text = self._format_audio_analysis(audio_result)
        vision_text = self._format_vision_analysis(vision_result)

        if not basic_info:
            basic_info = f"演员姓名：{actor_name or '未提供'}"

        available_text = ", ".join([
            "文本" if "text" in modalities else "",
            "音频" if "audio" in modalities else "",
            "视频" if "video" in modalities else "",
        ]).strip(", ")

        user_prompt = MULTIMODAL_USER_PROMPT_TEMPLATE.format(
            basic_info=basic_info,
            text_material=text_material or "无文本材料",
            audio_analysis=audio_text,
            vision_analysis=vision_text,
            available_modalities=available_text,
        )

        # 调用 LLM
        for attempt in range(max_retries + 1):
            if attempt > 0:
                print(f"  [重试 {attempt}/{max_retries}]...")

            result = self.llm.chat_json(MULTIMODAL_SYSTEM_PROMPT, user_prompt)

            if "_parse_error" in result:
                if attempt < max_retries:
                    continue
                print(f"  ❌ JSON 解析失败")
                break

            try:
                profile = ActorProfile.from_dict(result)
                if actor_name and not profile.actor_name:
                    profile.actor_name = actor_name
                profile.analysis_sources = modalities

                # 构建分析报告
                report = self._build_analysis_report(
                    actor_name=profile.actor_name,
                    modalities=modalities,
                    audio_result=audio_result,
                    vision_result=vision_result,
                )

                analysis_result = MultimodalAnalysisResult(
                    actor_profile=profile,
                    modalities_used=modalities,
                    audio_features=audio_result.acoustic_features if audio_result else None,
                    facial_features=vision_result.facial_features if vision_result else None,
                    body_features=vision_result.body_features if vision_result else None,
                    analysis_report=report,
                )

                print(f"  ✅ 多模态分析完成：{profile.actor_name}")
                print(f"     使用模态：{', '.join(modalities)}")
                return analysis_result

            except Exception as e:
                print(f"  ❌ 演员画像构建失败：{e}")
                if attempt < max_retries:
                    continue
                break

        # 失败时返回空结果
        return MultimodalAnalysisResult(
            actor_profile=ActorProfile(actor_name=actor_name, analysis_sources=modalities),
            modalities_used=modalities,
        )

    def _build_analysis_report(
        self,
        actor_name: str,
        modalities: List[str],
        audio_result: Optional[AudioAnalysisResult],
        vision_result: Optional[VisionAnalysisResult],
    ) -> str:
        """构建多模态分析报告"""
        lines = [
            f"=== CastingNuwa 多模态分析报告 ===",
            f"演员：{actor_name}",
            f"分析模态：{', '.join(modalities)}",
            f"",
        ]

        if audio_result:
            f = audio_result.acoustic_features
            lines.extend([
                f"【音频分析】",
                f"  时长：{f.duration:.1f}秒 | 转写：{audio_result.word_count}字",
                f"  音高：{f.pitch_category}",
                f"  音色：{f.timbre_category}",
                f"  语速：{f.pace_category} ({f.speech_rate:.0f}字/分钟)",
                f"  情感表达：{f.emotion_expression}",
                f"  优势：{', '.join(f.vocal_strengths) if f.vocal_strengths else '无'}",
                f"  局限：{', '.join(f.vocal_limitations) if f.vocal_limitations else '无'}",
                f"",
            ])

        if vision_result:
            ff = vision_result.facial_features
            bf = vision_result.body_features
            lines.extend([
                f"【视觉分析】",
                f"  帧数：{vision_result.frames_extracted}",
                f"  面部：{ff.expression_category} | 眼神：{ff.eye_contact_category}",
                f"  手势：{bf.gesture_category}",
                f"  姿态：{bf.posture_category}",
                f"  空间：{bf.spatial_category}",
                f"  面部优势：{', '.join(ff.facial_strengths) if ff.facial_strengths else '无'}",
                f"  肢体优势：{', '.join(bf.body_strengths) if bf.body_strengths else '无'}",
                f"",
            ])

        lines.append("=== 报告结束 ===")
        return "\n".join(lines)
