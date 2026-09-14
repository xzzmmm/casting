"""
CastingNuwa · 选角女娲
基于思维蒸馏的 AI 戏剧选角辅助系统

灵感来源：nuwa-skill（女娲.skill）—— 蒸馏任何人的思维方式
本项目迁移理念：蒸馏戏剧角色的认知操作系统，生成角色卡，辅助选角决策
"""

__version__ = "0.4.0"
__author__ = "CastingNuwa Team"

from .models import RoleCard
from .role_distiller import RoleDistiller
from .llm_client import LLMClient
from .actor_models import ActorProfile
from .actor_profiler import ActorProfiler
from .matching_engine import MatchingEngine, CastingReport, MatchResult
from .audio_processor import AudioProcessor, AudioAnalysisResult, AcousticFeatures
from .vision_processor import VisionProcessor, VisionAnalysisResult, FacialExpressionFeatures, BodyLanguageFeatures
from .multimodal_analyzer import MultimodalAnalyzer, MultimodalAnalysisResult
from .crew_analyzer import CrewAnalyzer
from .models import CrewAnalysisResult, CrewRequirement

__all__ = [
    "RoleCard", "RoleDistiller", "LLMClient",
    "ActorProfile", "ActorProfiler",
    "MatchingEngine", "CastingReport", "MatchResult",
    "AudioProcessor", "AudioAnalysisResult", "AcousticFeatures",
    "VisionProcessor", "VisionAnalysisResult", "FacialExpressionFeatures", "BodyLanguageFeatures",
    "MultimodalAnalyzer", "MultimodalAnalysisResult",
    "CrewAnalyzer", "CrewAnalysisResult", "CrewRequirement",
]
