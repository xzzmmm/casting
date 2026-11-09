"""排练处理管线：音频轨与视频轨先后处理，产出结构化数据后入库。

容错策略：
- LLM 结构化校验重试耗尽时，标记该排练为待人工复核（review_pending），
  原始转写落盘到 data/review_queue/，台位处理继续执行，不中断整条任务。
- 未接入的 AI 服务抛出 NotImplementedError 时，任务标记为 failed 并记录原因。
"""

from __future__ import annotations

import logging
from pathlib import Path

from sqlalchemy.orm import Session

from app.config import settings
from app.core.db import SessionLocal
from app.core.schemas import BlockingPointIn, LogItemCreate
from app.models import BlockingTrack, LogItem, Rehearsal
from app.services.asr import SenseVoiceTranscriber, TranscriptionSegment
from app.services.llm_struct import LogStructurer
from app.services.pose import YoloPoseDetector
from app.services.tracker import BlockingTracker

logger = logging.getLogger(__name__)


def _media_path(rehearsal: Rehearsal) -> Path:
    return settings.upload_dir / rehearsal.source_media


def _save_log_items(db: Session, rehearsal_id: int, items: list[LogItemCreate]) -> None:
    for item in items:
        db.add(LogItem(rehearsal_id=rehearsal_id, **item.model_dump()))


def _save_blocking(
    db: Session, rehearsal_id: int, points: list[BlockingPointIn]
) -> None:
    for point in points:
        db.add(BlockingTrack(rehearsal_id=rehearsal_id, **point.model_dump()))


def _save_transcript_for_review(
    rehearsal_id: int, transcript: list[TranscriptionSegment]
) -> Path:
    """把原始转写落盘，供后台看板人工复核。"""
    review_dir = settings.data_dir / "review_queue"
    review_dir.mkdir(parents=True, exist_ok=True)
    target = review_dir / f"rehearsal_{rehearsal_id}.txt"
    lines = [f"[{seg.start:.1f}-{seg.end:.1f}] {seg.text}" for seg in transcript]
    target.write_text("\n".join(lines), encoding="utf-8")
    return target


def _mark_review_pending(
    db: Session,
    rehearsal: Rehearsal,
    transcript: list[TranscriptionSegment],
    error: str,
) -> None:
    """LLM 结构化失败：保留原始转写并标记待人工复核，不抛异常。"""
    target = _save_transcript_for_review(rehearsal.id, transcript)
    rehearsal.review_pending = True
    rehearsal.review_note = f"LLM 结构化校验失败，转写已保存至 {target}；错误：{error}"
    db.commit()


def process_rehearsal(rehearsal_id: int) -> None:
    """后台处理单个排练：先日志后台位；任一环节失败则记录错误，不阻塞查询。"""
    db = SessionLocal()
    try:
        rehearsal = db.get(Rehearsal, rehearsal_id)
        if rehearsal is None:
            logger.warning("rehearsal %s not found", rehearsal_id)
            return
        rehearsal.status = "processing"
        db.commit()

        media = _media_path(rehearsal)

        transcriber = SenseVoiceTranscriber()
        transcript = transcriber.transcribe(media)

        structurer = LogStructurer()
        result = structurer.structure(
            transcript,
            play=rehearsal.play,
            rehearsal_no=rehearsal.rehearsal_no,
            date=rehearsal.date.strftime("%Y-%m-%d"),
        )
        if result.needs_manual_review:
            _mark_review_pending(db, rehearsal, transcript, result.error)
        else:
            _save_log_items(db, rehearsal.id, result.items)

        detector = YoloPoseDetector()
        detections = detector.detect(media)
        points = BlockingTracker().build(detections)
        _save_blocking(db, rehearsal.id, points)

        rehearsal.status = "done"
        db.commit()
    except NotImplementedError as exc:
        _mark_failed(db, rehearsal_id, str(exc))
        logger.info("rehearsal %s failed: %s", rehearsal_id, exc)
    except Exception as exc:  # noqa: BLE001 记录未知错误，保证任务状态可追踪
        _mark_failed(db, rehearsal_id, f"{type(exc).__name__}: {exc}")
        logger.exception("rehearsal %s failed", rehearsal_id)
    finally:
        db.close()


def _mark_failed(db: Session, rehearsal_id: int, message: str) -> None:
    db.rollback()
    rehearsal = db.get(Rehearsal, rehearsal_id)
    if rehearsal is not None:
        rehearsal.status = "failed"
        rehearsal.error_message = message
        db.commit()
