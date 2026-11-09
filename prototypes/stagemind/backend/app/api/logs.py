"""排练日志条目：查询与人工确认（修正/定稿）。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.schemas import LogItemOut, LogItemUpdate
from app.models import LogItem

router = APIRouter(tags=["logs"])


@router.get("/rehearsals/{rehearsal_id}/logs", response_model=list[LogItemOut])
def list_logs(rehearsal_id: int, db: Session = Depends(get_db)) -> list[LogItem]:
    stmt = (
        select(LogItem)
        .where(LogItem.rehearsal_id == rehearsal_id)
        .order_by(LogItem.ts_start)
    )
    return list(db.scalars(stmt))


@router.patch("/logs/{item_id}", response_model=LogItemOut)
def update_log_item(
    item_id: int, payload: LogItemUpdate, db: Session = Depends(get_db)
) -> LogItem:
    """人工确认或修正结构化结果后入库。"""
    item = db.get(LogItem, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="log item not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(item, field, value)
    db.commit()
    db.refresh(item)
    return item
