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

MULTIMODAL_SYSTEM_PROMPT = """你是一位选角观察助手，帮助导演整理试镜观察，而不是给演员打分下结论。

你的职责是把文本、声音、视觉三方面的材料整理成观察记录：
1. 记录可观察的事实（停顿、语速/音量变化、动作、表情、台词处理），标注时间或位置
2. 对事实提出可能的解释，同时保留其他解释
3. 区分直接观察、推断和无法判断
4. 建议下一轮如何验证（换什么指令、观察什么变化）

【必须区分三个概念】
- 特征强度：表演是否外放（风格，不是好坏）
- 表演质量：表达是否准确服务情境（需要导演判断，你只提供线索）
- 角色匹配：是否适合特定角色（不取决于性格相似度）

声音或动作变化只能作为观察线索，不能直接推出"演得好""情感真实"。
例如：停顿可能表达犹豫，也可能是回忆台词，需要在 verification_suggestion 中建议如何区分。

【模态缺失处理】
- 声学/视觉特征是客观数据，文本是主观描述，两者相互印证
- 某个模态缺失时，明确在 analysis_warnings 中说明，不要编造该模态的观察
- 材料不足的维度生成 verification_items（待验证项），不要硬给中等分
- 自我介绍自述放入 evidence.self_reports，与实际表演观察分开

输出必须是严格的 JSON 格式。
"""

MULTIMODAL_USER_PROMPT_TEMPLATE = """请整理以下演员试镜材料的多模态观察记录。

【演员基本信息】
{basic_info}

【文本材料】（自我介绍/试镜转写）
---
{text_material}
---

【音频分析结果】（客观声学特征）
---
{audio_analysis}
---

【视觉分析结果】（客观面部/肢体特征，可能因技术限制缺失）
---
{vision_analysis}
---

【可用模态】{available_modalities}

请输出观察记录 JSON，结构如下：
{{
  "actor_name": "演员姓名",
  "analysis_sources": ["text", "audio", "video"],
  "analysis_status": "complete / partial / failed",
  "analysis_warnings": ["缺失或降级的模态说明"],
  "basic_info": {{
    "name": "",
    "age_gender": "",
    "experience": "",
    "background": "",
    "self_description": ""
  }},
  "observations": [
    {{
      "timestamp": "时间段",
      "observed_behavior": "可观察事实（停顿/语速/音量/动作/表情）",
      "possible_interpretation": "可能意味着什么",
      "alternative_interpretations": ["其他解释"],
      "evidence_type": "直接观察/推断/无法判断",
      "confidence": "高/中/低/无法判断",
      "verification_suggestion": "下一轮怎么验证",
      "related_requirement": "",
      "source": "video/audio/text"
    }}
  ],
  "verification_items": [
    {{
      "item": "待验证能力",
      "why_needed": "对应什么要求",
      "current_evidence": "目前证据",
      "suggested_task": "补充试镜任务",
      "priority": "高/中/低"
    }}
  ],
  "evidence": {{
    "self_reports": ["自我介绍自述（未经表演验证）"],
    "past_experience": ["过往经历"],
    "material_gaps": ["材料缺失说明"]
  }},
  "adjustment_responses": [],
  "vocal_traits": {{
    "pitch": "", "timbre": "", "clarity": "", "pace": "",
    "resonance": "", "emotional_expression": "",
    "strengths": [], "limitations": []
  }},
  "facial_expressiveness": {{
    "expression_range": "", "micro_expression": "", "eye_contact": "",
    "facial_symmetry": "", "strengths": [], "limitations": []
  }},
  "physical_expressiveness": {{
    "gesture_richness": "", "posture_naturalness": "", "spatial_usage": "",
    "movement_flow": "", "body_awareness": "", "strengths": [], "limitations": []
  }},
  "emotional_range": {{
    "expressible_emotions": [], "emotional_depth": "", "transition_fluency": "",
    "strongest_emotions": [], "weakest_emotions": [], "notes": ""
  }},
  "temperament": {{
    "primary_type": "", "secondary_type": "", "overall_impression": "",
    "suitable_genres": [], "unsuitable_genres": []
  }},
  "acting_style": {{
    "style_tendency": "", "naturalness": "", "rhythm_sense": "",
    "line_delivery": "", "improvisation": "", "learning_ability": "",
    "experience_level": "", "potential": "", "development_suggestions": []
  }},
  "quantitative_traits": {{
    "extraversion": {{"score": null, "evidence_count": 0, "evidence": [], "confidence": "无法判断"}},
    "emotional_intensity": {{"score": null, "evidence_count": 0, "evidence": [], "confidence": "无法判断"}},
    "rationality": {{"score": null, "evidence_count": 0, "evidence": [], "confidence": "无法判断"}},
    "dominance": {{"score": null, "evidence_count": 0, "evidence": [], "confidence": "无法判断"}},
    "credibility": {{"score": null, "evidence_count": 0, "evidence": [], "confidence": "无法判断"}}
  }}
}}

请确保：
1. observations 至少3条，基于实际提供的声学/视觉/文本数据，不要编造缺失模态的观察
2. 视觉或音频数据缺失时，在 analysis_warnings 说明，并把相关能力放入 verification_items
3. 量化分数只反映特征强度，证据不足设为 null
4. 输出纯 JSON，不要有任何额外文字。
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
            f"采样覆盖：{getattr(vision_result, 'sampling_note', '') or '未记录'}",
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
        # 确定可用模态及降级状态
        modalities = []
        modality_warnings = []
        if text_material:
            modalities.append("text")
        if audio_result:
            modalities.append("audio")
            # 音频转写为空说明音频分析实际未成功
            if not getattr(audio_result, "transcript", "") and not text_material:
                modality_warnings.append("音频转写为空，可能无人声或转写失败")
        if vision_result:
            modalities.append("video")
            # 视觉分析降级（如 mediapipe solutions 不可用）
            vision_warnings = getattr(vision_result, "warnings", [])
            if vision_warnings:
                modality_warnings.extend(vision_warnings)

        print(f"\n{'='*60}")
        print(f"  CastingNuwa · 多模态观察记录")
        print(f"  演员：{actor_name or '未命名'}")
        print(f"  可用模态：{', '.join(modalities) if modalities else '无'}")
        if modality_warnings:
            for w in modality_warnings:
                print(f"  ⚠️  {w}")
        print(f"{'='*60}\n")

        if self.llm.is_mock_mode:
            print(f"  ⚠️  当前为 Mock 演示模式，结果为示例数据，不能作为真实选角依据")

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

                # 非演示模式下空画像视为无效：重试，仍为空则落到 failed 分支
                if not self.llm.is_mock_mode and not profile.has_substantive_content():
                    print("  ⚠️ 模型返回空观察记录，视为无效结果")
                    if attempt < max_retries:
                        continue
                    break

                # 设置分析状态：有降级警告则 partial，模态齐全无警告则 complete
                if modality_warnings:
                    profile.analysis_status = "partial"
                    for w in modality_warnings:
                        if w not in profile.analysis_warnings:
                            profile.analysis_warnings.append(w)
                else:
                    profile.analysis_status = "complete"

                # Mock 模式显式标记
                if self.llm.is_mock_mode:
                    profile.analysis_status = "demo"
                    if "当前为演示数据，非真实分析结果" not in profile.analysis_warnings:
                        profile.analysis_warnings.append("当前为演示数据，非真实分析结果")

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

                print(f"  ✅ 观察记录完成：{profile.actor_name}（状态：{profile.analysis_status}）")
                print(f"     观察记录 {len(profile.observations)} 条，待验证项 {len(profile.verification_items)} 条")
                return analysis_result

            except Exception as e:
                print(f"  ❌ 观察记录构建失败：{e}")
                if attempt < max_retries:
                    continue
                break

        # 失败时明确返回 failed 状态，不允许空画像冒充成功
        failed_profile = ActorProfile(
            actor_name=actor_name,
            analysis_sources=modalities,
            analysis_status="failed",
            analysis_warnings=["分析失败，未生成有效观察记录，请重试或检查材料/API配置"],
        )
        return MultimodalAnalysisResult(
            actor_profile=failed_profile,
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
