"""SQLAlchemy ORM 模型。"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


def _utcnow() -> datetime:
    """返回无时区的 UTC 时间，兼容 SQLite DateTime 列。"""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Rehearsal(Base):
    """一次排练场次。"""

    __tablename__ = "rehearsals"

    id: Mapped[int] = mapped_column(primary_key=True)
    play: Mapped[str] = mapped_column(String(120))
    rehearsal_no: Mapped[int]
    date: Mapped[datetime] = mapped_column(DateTime)
    source_media: Mapped[str] = mapped_column(String(255), default="")
    status: Mapped[str] = mapped_column(String(20), default="pending")
    error_message: Mapped[str] = mapped_column(Text, default="")
    review_pending: Mapped[bool] = mapped_column(Boolean, default=False)
    review_note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    items: Mapped[list[LogItem]] = relationship(
        back_populates="rehearsal", cascade="all, delete-orphan"
    )
    tracks: Mapped[list[BlockingTrack]] = relationship(
        back_populates="rehearsal", cascade="all, delete-orphan"
    )
    issues: Mapped[list[Issue]] = relationship(
        back_populates="rehearsal", cascade="all, delete-orphan"
    )


class LogItem(Base):
    """结构化排练日志条目。"""

    __tablename__ = "log_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    rehearsal_id: Mapped[int] = mapped_column(ForeignKey("rehearsals.id"))
    ts_start: Mapped[float]
    ts_end: Mapped[float]
    item_type: Mapped[str] = mapped_column(String(20))
    speakers: Mapped[list[str]] = mapped_column(JSON, default=list)
    summary: Mapped[str] = mapped_column(Text)
    decision: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(10), default="已确定")
    actors: Mapped[list[str]] = mapped_column(JSON, default=list)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)

    rehearsal: Mapped[Rehearsal] = relationship(back_populates="items")


class BlockingTrack(Base):
    """台位轨迹点：同一演员按 frame_ts 升序即为其动线。"""

    __tablename__ = "blocking_tracks"

    id: Mapped[int] = mapped_column(primary_key=True)
    rehearsal_id: Mapped[int] = mapped_column(ForeignKey("rehearsals.id"))
    actor: Mapped[str] = mapped_column(String(60))
    frame_ts: Mapped[float]
    x: Mapped[float]
    y: Mapped[float]
    confidence: Mapped[float]

    rehearsal: Mapped[Rehearsal] = relationship(back_populates="tracks")


class Issue(Base):
    """跨排练跟踪的问题条目。"""

    __tablename__ = "issues"

    id: Mapped[int] = mapped_column(primary_key=True)
    rehearsal_id: Mapped[int] = mapped_column(ForeignKey("rehearsals.id"))
    source_item_id: Mapped[int | None]
    description: Mapped[str] = mapped_column(Text)
    owner: Mapped[str] = mapped_column(String(60), default="")
    status: Mapped[str] = mapped_column(String(10), default="open")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    rehearsal: Mapped[Rehearsal] = relationship(back_populates="issues")
