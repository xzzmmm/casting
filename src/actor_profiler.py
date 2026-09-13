"""
CastingNuwa · 选角女娲
演员画像器（Actor Profiler）

从演员的自我介绍、试镜转写文本等材料中，
分析演员的多维度特质，生成演员画像。

当前版本支持文本输入分析，视频/音频分析为可扩展接口。
"""

import os
import json
from typing import Optional, List

from .actor_models import ActorProfile
from .actor_prompts import ACTOR_SYSTEM_PROMPT, ACTOR_USER_PROMPT_TEMPLATE
from .llm_client import LLMClient


class ActorProfiler:
    """演员画像器"""

    def __init__(self, llm_client: Optional[LLMClient] = None):
        self.llm = llm_client or LLMClient()

    def profile_from_text(
        self,
        actor_material: str,
        actor_name: str = "",
        material_note: str = "以下为演员的自我介绍和试镜转写文本。",
        max_retries: int = 2,
    ) -> Optional[ActorProfile]:
        """
        从文本材料生成演员画像

        Args:
            actor_material: 演员材料（自我介绍+试镜转写等）
            actor_name: 演员姓名（可选，材料中没有时使用）
            material_note: 材料说明
            max_retries: 最大重试次数

        Returns:
            演员画像，失败返回 None
        """
        print(f"\n{'='*60}")
        print(f"  CastingNuwa · 演员画像（文本模式）")
        print(f"  目标：{actor_name or '未命名演员'}")
        print(f"{'='*60}\n")

        if self.llm.is_mock_mode:
            print(f"  ⚠️  当前为 Mock 演示模式，输出为示例数据")

        user_prompt = ACTOR_USER_PROMPT_TEMPLATE.format(
            actor_material=actor_material,
            material_note=material_note,
        )

        for attempt in range(max_retries + 1):
            if attempt > 0:
                print(f"  [重试 {attempt}/{max_retries}]...")

            result = self.llm.chat_json(ACTOR_SYSTEM_PROMPT, user_prompt)

            if "_parse_error" in result:
                if attempt < max_retries:
                    continue
                print(f"  ❌ JSON 解析失败")
                return None

            try:
                profile = ActorProfile.from_dict(result)
                if actor_name and not profile.actor_name:
                    profile.actor_name = actor_name
                if "text" not in profile.analysis_sources:
                    profile.analysis_sources.append("text")
                print(f"  ✅ 演员画像生成完成：{profile.actor_name}\n")
                return profile
            except Exception as e:
                print(f"  ❌ 演员画像构建失败：{e}")
                if attempt < max_retries:
                    continue
                return None

        return None

    def profile_from_audio(
        self,
        audio_path: str,
        actor_name: str = "",
        text_material: str = "",
        language: str = "zh",
        max_retries: int = 2,
    ) -> Optional[ActorProfile]:
        """
        从音频文件生成演员画像（文本+音频双模态）

        Args:
            audio_path: 音频文件路径
            actor_name: 演员姓名
            text_material: 额外的文本材料（自我介绍等）
            language: 语言
            max_retries: 最大重试次数

        Returns:
            演员画像
        """
        from .audio_processor import AudioProcessor
        from .multimodal_analyzer import MultimodalAnalyzer

        print(f"\n{'='*60}")
        print(f"  CastingNuwa · 演员画像（音频模式）")
        print(f"  音频文件：{audio_path}")
        print(f"{'='*60}\n")

        # 音频分析
        audio_processor = AudioProcessor()
        audio_result = audio_processor.analyze(audio_path, language=language)

        # 合并文本材料
        combined_text = text_material
        if audio_result.transcript:
            if combined_text:
                combined_text += "\n\n【试镜转写】\n" + audio_result.transcript
            else:
                combined_text = "【试镜转写】\n" + audio_result.transcript

        # 多模态分析
        multimodal = MultimodalAnalyzer(llm_client=self.llm)
        result = multimodal.analyze(
            actor_name=actor_name,
            text_material=combined_text,
            audio_result=audio_result,
            vision_result=None,
        )

        return result.actor_profile if result.actor_profile.actor_name else None

    def profile_from_video(
        self,
        video_path: str,
        actor_name: str = "",
        text_material: str = "",
        language: str = "zh",
        max_frames: int = 30,
        max_retries: int = 2,
    ) -> Optional[ActorProfile]:
        """
        从视频文件生成演员画像（文本+音频+视频三模态）

        Args:
            video_path: 视频文件路径
            actor_name: 演员姓名
            text_material: 额外的文本材料（自我介绍等）
            language: 语言
            max_frames: 最大分析帧数
            max_retries: 最大重试次数

        Returns:
            演员画像
        """
        from .audio_processor import AudioProcessor
        from .vision_processor import VisionProcessor
        from .multimodal_analyzer import MultimodalAnalyzer

        print(f"\n{'='*60}")
        print(f"  CastingNuwa · 演员画像（视频模式·三模态）")
        print(f"  视频文件：{video_path}")
        print(f"{'='*60}\n")

        # 音频分析（从视频提取）
        audio_processor = AudioProcessor()
        audio_result = audio_processor.analyze_video(video_path, language=language)

        # 视觉分析
        vision_processor = VisionProcessor(max_frames=max_frames)
        vision_result = vision_processor.analyze_video(video_path)
        vision_processor.close()

        # 合并文本材料
        combined_text = text_material
        if audio_result.transcript:
            if combined_text:
                combined_text += "\n\n【试镜转写】\n" + audio_result.transcript
            else:
                combined_text = "【试镜转写】\n" + audio_result.transcript

        # 多模态分析
        multimodal = MultimodalAnalyzer(llm_client=self.llm)
        result = multimodal.analyze(
            actor_name=actor_name,
            text_material=combined_text,
            audio_result=audio_result,
            vision_result=vision_result,
        )

        return result.actor_profile if result.actor_profile.actor_name else None

    @staticmethod
    def save_profiles(profiles: List[ActorProfile], output_path: str) -> str:
        """保存演员画像列表到 JSON 文件"""
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

        data = {
            "project": "CastingNuwa · 选角女娲",
            "description": "演员画像集合",
            "actor_count": len(profiles),
            "actors": [p.to_dict() for p in profiles],
        }

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        print(f"  💾 演员画像已保存：{output_path}")
        return output_path

    @staticmethod
    def load_profiles(input_path: str) -> List[ActorProfile]:
        """从 JSON 文件加载演员画像"""
        with open(input_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        actors_data = data.get("actors", [])
        return [ActorProfile.from_dict(ad) for ad in actors_data]

    @staticmethod
    def print_summary(profiles: List[ActorProfile]) -> None:
        """打印所有演员画像摘要"""
        for profile in profiles:
            print(profile.summary())
            print()
