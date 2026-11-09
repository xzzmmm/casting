"""API 请求/响应模型（Pydantic），与 docs/data_schema.md 保持一致。"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ItemStatus = Literal["已确定", "待解决"]
IssueStatus = Literal["open", "resolved"]


class RehearsalCreate(BaseModel):
    play: str
    rehearsal_no: int = Field(ge=1)
    date: datetime


class RehearsalOut(RehearsalCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source_media: str
    status: str
    error_message: str = ""
    review_pending: bool = False
    review_note: str = ""


class RehearsalUpdate(BaseModel):
    """排练场次更新；目前仅支持修改排练日期。"""

    date: datetime


class LogItemCreate(BaseModel):
    ts_start: float = Field(ge=0)
    ts_end: float = Field(ge=0)
    item_type: str
    speakers: list[str] = Field(default_factory=list)
    summary: str
    decision: str = ""
    status: ItemStatus = "已确定"
    actors: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)


class LogItemUpdate(BaseModel):
    summary: str | None = None
    decision: str | None = None
    status: ItemStatus | None = None


class LogItemOut(LogItemCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    rehearsal_id: int


class BlockingPointIn(BaseModel):
    actor: str
    frame_ts: float = Field(ge=0)
    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)
    confidence: float = Field(ge=0, le=1)


class BlockingPointOut(BlockingPointIn):
    model_config = ConfigDict(from_attributes=True)

    id: int
    rehearsal_id: int


class IssueCreate(BaseModel):
    rehearsal_id: int
    description: str = Field(min_length=1)
    owner: str = ""
    source_item_id: int | None = None


class IssueUpdate(BaseModel):
    status: IssueStatus


class IssueOut(IssueCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: str
    created_at: datetime
    resolved_at: datetime | None = None
