"""W3 集成测试：真实 ASR 接入后，整条管线产出结构化日志。"""

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
from app.models import LogItem, Rehearsal
from app.services import llm_client

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEMO_AUDIO = PROJECT_ROOT / "data" / "test_data" / "rehearsal_demo.wav"

VALID_ITEMS = [
    {
        "ts_start": 0.0,
        "ts_end": 5.0,
        "item_type": "道具",
        "speakers": ["导演"],
        "summary": "带椅子和桌子",
        "decision": "明天布置",
        "status": "待解决",
        "actors": [],
        "tags": ["道具"],
    }
]


@pytest.mark.skipif(not DEMO_AUDIO.exists(), reason="缺少示例音频，跳过集成测试")
def test_process_rehearsal_full_chain_with_real_asr(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """真实 ASR 转写 + fake 台位/LLM：日志入库、任务 done、无复核标记。"""
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
            source_media="demo.wav",
            status="pending",
        )
        db.add(rehearsal)
        db.commit()
        rehearsal_id = rehearsal.id

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
    (tmp_settings.upload_dir / "demo.wav").write_bytes(DEMO_AUDIO.read_bytes())

    monkeypatch.setattr(pipeline, "settings", tmp_settings)
    monkeypatch.setattr(pipeline, "SessionLocal", testing_session)
    monkeypatch.setattr(
        llm_client,
        "call_llm_api",
        lambda prompt, system_prompt: json.dumps(VALID_ITEMS, ensure_ascii=False),
    )
    monkeypatch.setattr(pipeline, "YoloPoseDetector", FakeDetector)
    monkeypatch.setattr(pipeline, "BlockingTracker", FakeTracker)

    pipeline.process_rehearsal(rehearsal_id)

    with testing_session() as db:
        stored = db.get(Rehearsal, rehearsal_id)
        assert stored.status == "done"
        assert stored.review_pending is False
        logs = db.query(LogItem).filter_by(rehearsal_id=rehearsal_id).all()
        assert len(logs) == 1
        assert logs[0].summary == "带椅子和桌子"
