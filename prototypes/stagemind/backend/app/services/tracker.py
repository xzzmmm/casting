"""台位轨迹构建：将单帧检测点聚合成演员动线。

当前版本为直接映射：每个检测点转为台位记录，供前端按演员分组展示。
W6-W8 在此之上做跨帧关联（ID 保持）与轨迹平滑。
"""

from __future__ import annotations

from app.core.schemas import BlockingPointIn
from app.services.pose import Detection


class BlockingTracker:
    """把检测序列整理为按演员分组的动线点。"""

    def build(self, detections: list[Detection]) -> list[BlockingPointIn]:
        points = [
            BlockingPointIn(
                actor=d.actor_id,
                frame_ts=d.frame_ts,
                x=d.x,
                y=d.y,
                confidence=d.confidence,
            )
            for d in detections
        ]
        points.sort(key=lambda p: (p.actor, p.frame_ts))
        return points
