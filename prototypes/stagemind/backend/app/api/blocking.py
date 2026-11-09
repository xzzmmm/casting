"""台位轨迹：按排练查询动线点。"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.schemas import BlockingPointOut
from app.models import BlockingTrack

router = APIRouter(tags=["blocking"])


@router.get(
    "/rehearsals/{rehearsal_id}/blocking", response_model=list[BlockingPointOut]
)
def list_blocking(rehearsal_id: int, db: Session = Depends(get_db)) -> list[BlockingTrack]:
    stmt = (
        select(BlockingTrack)
        .where(BlockingTrack.rehearsal_id == rehearsal_id)
        .order_by(BlockingTrack.frame_ts)
    )
    return list(db.scalars(stmt))
