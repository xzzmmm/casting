"""排练场次资源：列表、详情与日期变更提醒。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.schemas import RehearsalOut, RehearsalUpdate
from app.models import Rehearsal
from app.services.notify import send_date_change_notice

router = APIRouter(prefix="/rehearsals", tags=["rehearsals"])


@router.get("", response_model=list[RehearsalOut])
def list_rehearsals(
    review_pending: bool | None = None, db: Session = Depends(get_db)
) -> list[Rehearsal]:
    """按需过滤待人工复核的排练场次。"""
    stmt = select(Rehearsal).order_by(Rehearsal.created_at.desc())
    if review_pending is not None:
        stmt = stmt.where(Rehearsal.review_pending.is_(review_pending))
    return list(db.scalars(stmt))


@router.get("/{rehearsal_id}", response_model=RehearsalOut)
def get_rehearsal(rehearsal_id: int, db: Session = Depends(get_db)) -> Rehearsal:
    rehearsal = db.get(Rehearsal, rehearsal_id)
    if rehearsal is None:
        raise HTTPException(status_code=404, detail="rehearsal not found")
    return rehearsal


@router.patch("/{rehearsal_id}", response_model=RehearsalOut)
def update_rehearsal_date(
    rehearsal_id: int, payload: RehearsalUpdate, db: Session = Depends(get_db)
) -> Rehearsal:
    """修改排练日期；日期确实变化时通知全体成员。"""
    rehearsal = db.get(Rehearsal, rehearsal_id)
    if rehearsal is None:
        raise HTTPException(status_code=404, detail="rehearsal not found")

    old_date = rehearsal.date
    rehearsal.date = payload.date
    db.commit()
    db.refresh(rehearsal)

    if old_date != payload.date:
        send_date_change_notice(rehearsal, old_date, payload.date)
    return rehearsal
