"""排练上传：保存媒体文件并创建处理任务。"""

from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.config import settings
from app.core.db import get_db
from app.core.schemas import RehearsalOut
from app.models import Rehearsal
from app.worker.tasks import enqueue

router = APIRouter(prefix="/upload", tags=["upload"])


@router.post("", response_model=RehearsalOut, status_code=201)
def upload_rehearsal(
    play: str = Form(...),
    rehearsal_no: int = Form(...),
    date: str = Form(...),
    media: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> Rehearsal:
    """保存上传文件并登记排练场次，随后异步进入处理管线。"""
    try:
        parsed_date = datetime.strptime(date, "%Y-%m-%d")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="date 格式应为 YYYY-MM-DD") from exc

    suffix = Path(media.filename or "media").suffix
    stored_name = f"{uuid4().hex}{suffix}"
    target = settings.upload_dir / stored_name
    with target.open("wb") as buffer:
        shutil.copyfileobj(media.file, buffer)

    rehearsal = Rehearsal(
        play=play,
        rehearsal_no=rehearsal_no,
        date=parsed_date,
        source_media=stored_name,
        status="pending",
    )
    db.add(rehearsal)
    db.commit()
    db.refresh(rehearsal)

    enqueue(rehearsal.id)
    return rehearsal
