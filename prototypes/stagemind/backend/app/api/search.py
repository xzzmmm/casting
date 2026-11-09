"""检索：关键词 / 类型 / 演员组合过滤日志条目。"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import String, cast, or_, select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.schemas import LogItemOut
from app.models import LogItem

router = APIRouter(prefix="/search", tags=["search"])


@router.get("", response_model=list[LogItemOut])
def search_logs(
    q: str = "",
    item_type: str = "",
    actor: str = "",
    db: Session = Depends(get_db),
) -> list[LogItem]:
    """按关键词（摘要/结论）、条目类型、演员组合检索。"""
    stmt = select(LogItem)
    if q:
        pattern = f"%{q}%"
        stmt = stmt.where(
            or_(LogItem.summary.like(pattern), LogItem.decision.like(pattern))
        )
    if item_type:
        stmt = stmt.where(LogItem.item_type == item_type)
    if actor:
        # JSON 数组按文本匹配，如 ["甲","乙"] 匹配 "甲"
        stmt = stmt.where(cast(LogItem.actors, String).like(f'%"{actor}"%'))
    stmt = stmt.order_by(LogItem.rehearsal_id.desc(), LogItem.ts_start)
    return list(db.scalars(stmt))
