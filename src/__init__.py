"""
CastingNuwa · 选角女娲
基于思维蒸馏的 AI 戏剧选角辅助系统（v0.5 观察记录体系）

灵感来源：nuwa-skill（女娲.skill）—— 蒸馏任何人的思维方式
本项目迁移理念：蒸馏戏剧角色的认知操作系统，生成角色卡，辅助选角决策

v0.5 核心变化：
- 从"AI打分"改为"引导完成选角并说明依据"
- 输出观察记录（发生了什么→可能意味着什么→依据是否充分→下一轮怎么验证）
- 匹配结果改为候选方案+证据比较，而非单一排名
"""

__version__ = "0.5.0"
__author__ = "CastingNuwa Team"

from .models import (
    RoleCard, ObservableRequirement, ProductionSettings,
    AuditionTask, ObservationFocus,
)
from .role_distiller import RoleDistiller
from .llm_client import LLMClient
from .actor_models import (
    ActorProfile, ObservationRecord, VerificationItem,
    EvidenceCollection, AdjustmentResponse,
)
from .actor_profiler import ActorProfiler
from .matching_engine import (
    MatchingEngine, CastingReport, CastingProposal,
    EvidenceComparison, RoleCastingResult,
)
from .audio_processor import AudioProcessor, AudioAnalysisResult, AcousticFeatures
from .vision_processor import VisionProcessor, VisionAnalysisResult, FacialExpressionFeatures, BodyLanguageFeatures
from .multimodal_analyzer import MultimodalAnalyzer, MultimodalAnalysisResult
from .crew_analyzer import CrewAnalyzer
from .models import CrewAnalysisResult, CrewRequirement

__all__ = [
    # 角色蒸馏
    "RoleCard", "ObservableRequirement", "ProductionSettings",
    "AuditionTask", "ObservationFocus", "RoleDistiller",
    # LLM
    "LLMClient",
    # 演员观察记录
    "ActorProfile", "ObservationRecord", "VerificationItem",
    "EvidenceCollection", "AdjustmentResponse", "ActorProfiler",
    # 候选方案
    "MatchingEngine", "CastingReport", "CastingProposal",
    "EvidenceComparison", "RoleCastingResult",
    # 多模态
    "AudioProcessor", "AudioAnalysisResult", "AcousticFeatures",
    "VisionProcessor", "VisionAnalysisResult", "FacialExpressionFeatures", "BodyLanguageFeatures",
    "MultimodalAnalyzer", "MultimodalAnalysisResult",
    # 制作团队
    "CrewAnalyzer", "CrewAnalysisResult", "CrewRequirement",
]
