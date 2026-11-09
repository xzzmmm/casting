"""API 冒烟测试：不依赖真实 AI 模型。"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.worker.tasks as tasks
from app.core.db import Base, get_db
from app.main import create_app

TEST_FILE = ("clip.mp4", b"fake-video-content", "video/mp4")
TEST_FORM = {"play": "某某剧", "rehearsal_no": "5", "date": "2026-10-12"}


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """使用独立临时数据库，并禁用后台任务。"""
    engine = create_engine(
        f"sqlite:///{tmp_path / 'test.db'}",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    testing_session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    def override_get_db():
        db = testing_session()
        try:
            yield db
        finally:
            db.close()

    monkeypatch.setattr(tasks, "enqueue", lambda rehearsal_id: None)

    app = create_app()
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def _create_rehearsal(client: TestClient) -> dict:
    response = client.post("/api/upload", files={"media": TEST_FILE}, data=TEST_FORM)
    assert response.status_code == 201
    return response.json()


def test_health(client: TestClient) -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_upload_creates_rehearsal(client: TestClient) -> None:
    rehearsal = _create_rehearsal(client)
    assert rehearsal["play"] == "某某剧"
    assert rehearsal["rehearsal_no"] == 5
    assert rehearsal["status"] == "pending"


def test_upload_rejects_bad_date(client: TestClient) -> None:
    response = client.post(
        "/api/upload",
        files={"media": TEST_FILE},
        data={**TEST_FORM, "date": "2026/10/12"},
    )
    assert response.status_code == 400


def test_issue_roundtrip(client: TestClient) -> None:
    rehearsal = _create_rehearsal(client)

    create_response = client.post(
        "/api/issues",
        json={
            "rehearsal_id": rehearsal["id"],
            "description": "第二幕开场重音问题",
            "owner": "导演",
        },
    )
    assert create_response.status_code == 201
    issue_id = create_response.json()["id"]

    resolve_response = client.patch(
        f"/api/issues/{issue_id}", json={"status": "resolved"}
    )
    assert resolve_response.status_code == 200
    assert resolve_response.json()["status"] == "resolved"
    assert resolve_response.json()["resolved_at"] is not None

    list_response = client.get("/api/issues", params={"status": "resolved"})
    assert any(item["id"] == issue_id for item in list_response.json())
