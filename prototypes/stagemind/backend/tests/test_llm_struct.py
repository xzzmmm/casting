"""LLM 结构化：JSON 清洗、Schema 校验、失败重试与人工复核标记。"""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import datetime
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.services.pipeline as pipeline
from app.core.db import Base
from app.models import Rehearsal
from app.services import llm_client
from app.services.asr import TranscriptionSegment
from app.services.llm_struct import LogStructurer

VALID_ITEMS = [
    {
        "ts_start": 0.0,
        "ts_end": 5.0,
        "item_type": "道具",
        "speakers": ["导演"],
        "summary": "明天带椅子",
        "decision": "下周布置",
        "status": "待解决",
        "actors": [],
        "tags": ["道具"],
    }
]
VALID_PAYLOAD = json.dumps(VALID_ITEMS, ensure_ascii=False)


def _segments() -> list[TranscriptionSegment]:
    return [TranscriptionSegment(0.0, 5.0, "导演：明天带椅子")]


def test_extract_json_from_text_cleans_markdown() -> None:
    raw = "```json\n" + VALID_PAYLOAD + "\n```"
    cleaned = llm_client.extract_json_from_text(raw)
    assert json.loads(cleaned) == VALID_ITEMS


def test_structure_succeeds_on_first_try(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        llm_client, "call_llm_api", lambda prompt, system_prompt: VALID_PAYLOAD
    )
    result = LogStructurer().structure(_segments())
    assert result.needs_manual_review is False
    assert len(result.items) == 1
    assert result.items[0].summary == "明天带椅子"


def test_structure_retries_then_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"count": 0}

    def fake_call(prompt: str, system_prompt: str) -> str:
        calls["count"] += 1
        return "这不是 JSON" if calls["count"] == 1 else VALID_PAYLOAD

    monkeypatch.setattr(llm_client, "call_llm_api", fake_call)
    result = LogStructurer().structure(_segments())
    assert calls["count"] == 2
    assert result.needs_manual_review is False
    assert len(result.items) == 1


def test_structure_marks_review_after_retries_exhausted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        llm_client, "call_llm_api", lambda prompt, system_prompt: "坏数据"
    )
    result = LogStructurer().structure(_segments())
    assert result.needs_manual_review is True
    assert result.error is not None
    assert result.items == []


def test_process_rehearsal_marks_review_pending(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """校验失败时：标记复核、落盘转写、台位照常处理、任务不中断。"""
    engine = create_engine(
        f"sqlite:///{tmp_path / 'test.db'}",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    testing_session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    with testing_session() as db:
        rehearsal = Rehearsal(
            play="某某剧",
            rehearsal_no=1,
            date=datetime(2026, 10, 12),
            source_media="demo.mp4",
            status="pending",
        )
        db.add(rehearsal)
        db.commit()
        rehearsal_id = rehearsal.id

    class FakeTranscriber:
        def transcribe(self, media_path: Path) -> list[TranscriptionSegment]:
            return _segments()

    class FakeDetector:
        def detect(self, media_path: Path) -> list:
            return []

    class FakeTracker:
        def build(self, detections: list) -> list:
            return []

    tmp_settings = replace(
        pipeline.settings,
        data_dir=tmp_path / "data",
        upload_dir=tmp_path / "data" / "uploads",
    )
    (tmp_settings.upload_dir / "demo.mp4").write_bytes(b"fake")

    monkeypatch.setattr(pipeline, "settings", tmp_settings)
    monkeypatch.setattr(pipeline, "SessionLocal", testing_session)
    monkeypatch.setattr(
        llm_client, "call_llm_api", lambda prompt, system_prompt: "坏数据"
    )
    monkeypatch.setattr(pipeline, "SenseVoiceTranscriber", FakeTranscriber)
    monkeypatch.setattr(pipeline, "YoloPoseDetector", FakeDetector)
    monkeypatch.setattr(pipeline, "BlockingTracker", FakeTracker)

    pipeline.process_rehearsal(rehearsal_id)

    with testing_session() as db:
        stored = db.get(Rehearsal, rehearsal_id)
        assert stored.status == "done"
        assert stored.review_pending is True
        assert "LLM" in stored.review_note

    review_file = tmp_settings.data_dir / "review_queue" / f"rehearsal_{rehearsal_id}.txt"
    assert review_file.exists()
    assert "明天带椅子" in review_file.read_text(encoding="utf-8")
