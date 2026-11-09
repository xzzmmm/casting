"""日期变更提醒：PATCH 接口触发通知，webhook 缺失或失败均不中断主流程。"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.services.notify as notify
from app.core.db import Base, get_db
from app.main import create_app
from app.models import Rehearsal

WEBHOOK = "https://example.com/hook"


def _make_client(tmp_path: Path) -> tuple[TestClient, int]:
    engine = create_engine(
        f"sqlite:///{tmp_path / 'test.db'}",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with session() as db:
        rehearsal = Rehearsal(
            play="甲剧",
            rehearsal_no=1,
            date=datetime(2026, 10, 1),
            source_media="x.wav",
            status="pending",
        )
        db.add(rehearsal)
        db.commit()
        rehearsal_id = rehearsal.id

    def override_get_db():
        db = session()
        try:
            yield db
        finally:
            db.close()

    app = create_app()
    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app), rehearsal_id


class _FakeResponse:
    def raise_for_status(self) -> None:
        return None


def test_patch_date_sends_webhook_notice(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[dict] = []

    def fake_post(url: str, json: dict, timeout: float) -> _FakeResponse:
        calls.append({"url": url, "json": json})
        return _FakeResponse()

    monkeypatch.setattr(
        notify, "settings", replace(notify.settings, reminder_webhook_url=WEBHOOK)
    )
    monkeypatch.setattr(httpx, "post", fake_post)

    client, rehearsal_id = _make_client(tmp_path)
    response = client.patch(
        f"/api/rehearsals/{rehearsal_id}", json={"date": "2026-10-03"}
    )

    assert response.status_code == 200
    assert len(calls) == 1
    assert calls[0]["url"] == WEBHOOK
    text = calls[0]["json"]["content"]["text"]
    assert "甲剧" in text and "2026-10-01" in text and "2026-10-03" in text


def test_patch_same_date_no_notice(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[dict] = []

    def fake_post(url: str, json: dict, timeout: float) -> _FakeResponse:
        calls.append({"url": url, "json": json})
        return _FakeResponse()

    monkeypatch.setattr(
        notify, "settings", replace(notify.settings, reminder_webhook_url=WEBHOOK)
    )
    monkeypatch.setattr(httpx, "post", fake_post)

    client, rehearsal_id = _make_client(tmp_path)
    response = client.patch(
        f"/api/rehearsals/{rehearsal_id}", json={"date": "2026-10-01"}
    )

    assert response.status_code == 200
    assert calls == []


def test_notify_without_webhook_logs_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict] = []

    def fake_post(url: str, json: dict, timeout: float) -> _FakeResponse:
        calls.append({"url": url})
        return _FakeResponse()

    monkeypatch.setattr(
        notify, "settings", replace(notify.settings, reminder_webhook_url="")
    )
    monkeypatch.setattr(httpx, "post", fake_post)

    rehearsal = Rehearsal(
        play="乙剧",
        rehearsal_no=2,
        date=datetime(2026, 10, 5),
        source_media="x.wav",
        status="pending",
    )
    notify.send_date_change_notice(
        rehearsal, datetime(2026, 10, 5), datetime(2026, 10, 6)
    )
    assert calls == []


def test_notify_webhook_failure_swallowed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_post(url: str, json: dict, timeout: float):
        raise httpx.ConnectError("network down")

    monkeypatch.setattr(
        notify, "settings", replace(notify.settings, reminder_webhook_url=WEBHOOK)
    )
    monkeypatch.setattr(httpx, "post", fake_post)

    rehearsal = Rehearsal(
        play="丙剧",
        rehearsal_no=3,
        date=datetime(2026, 10, 5),
        source_media="x.wav",
        status="pending",
    )
    notify.send_date_change_notice(
        rehearsal, datetime(2026, 10, 5), datetime(2026, 10, 7)
    )
