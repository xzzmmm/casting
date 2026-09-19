"""
CastingNuwa · 选角女娲
基于思维蒸馏的 AI 戏剧选角辅助系统（v0.6 引导式选角流程）

灵感来源：nuwa-skill（女娲.skill）—— 蒸馏任何人的思维方式
本项目迁移理念：蒸馏戏剧角色的认知操作系统，生成角色卡，辅助选角决策

v0.5 核心变化：
- 从"AI打分"改为"引导完成选角并说明依据"
- 输出观察记录（发生了什么→可能意味着什么→依据是否充分→下一轮怎么验证）
- 匹配结果改为候选方案+证据比较，而非单一排名

v0.6 核心变化：
- 新增"选角设定"录入与负责人确认卡点（必须满足/可排练/反串/兼角/档期）
- 新增两轮试镜任务生成（统一材料+观察重点+调整指令+复试）
- 演员观察支持指导后复试记录与档期存档
- 候选方案支持兼角/档期/对手戏检查与人工确认、保存理由
- 会话隔离 + 项目 JSON 保存/加载 + 剧本更新提示重算
- 真实 API 失败明确报错，不再静默回退演示数据
- 视频改为全片均匀采样并保留时间戳
"""

__version__ = "0.6.0"
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
from .audition_designer import AuditionDesigner
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
    # 试镜任务
    "AuditionDesigner",
]
