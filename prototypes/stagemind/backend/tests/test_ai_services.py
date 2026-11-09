"""W3 接入测试：ASR 标签清洗与真实转写、姿态检测真实推理、台位映射。"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.core.schemas import BlockingPointIn
from app.services.asr import SenseVoiceTranscriber
from app.services.pose import Detection, YoloPoseDetector
from app.services.tracker import BlockingTracker

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEMO_AUDIO = PROJECT_ROOT / "data" / "test_data" / "rehearsal_demo.wav"
DEMO_IMAGE = PROJECT_ROOT / "data" / "test_data" / "stage_demo.jpg"


def test_clean_text_removes_language_tags() -> None:
    raw = "<|zh|><|NEUTRAL|><|Speech|><|woitn|>欢迎大家来体验"
    assert SenseVoiceTranscriber.clean_text(raw) == "欢迎大家来体验"


def test_sensevoice_real_transcribe() -> None:
    """真实模型：11 秒中文示例音频应产出清洗后的时间戳文本。"""
    if not DEMO_AUDIO.exists():
        pytest.skip("缺少示例音频，跳过真实转写测试")

    segments = SenseVoiceTranscriber().transcribe(DEMO_AUDIO)
    assert len(segments) == 1
    segment = segments[0]
    assert "<|" not in segment.text
    assert "欢迎大家" in segment.text
    assert 0 <= segment.start < segment.end


def test_yolo_real_detect_filters_low_confidence() -> None:
    """真实模型：多人图应检出多个台位点，且全部达到置信阈值。"""
    if not DEMO_IMAGE.exists():
        pytest.skip("缺少示例图片，跳过真实检测测试")

    detections = YoloPoseDetector().detect(DEMO_IMAGE)
    assert len(detections) >= 2
    assert all(d.confidence >= 0.5 for d in detections)
    assert all(0 <= d.x <= 1 and 0 <= d.y <= 1 for d in detections)
    actors = {d.actor_id for d in detections}
    assert len(actors) == len(detections)


def test_tracker_maps_detections_to_points() -> None:
    detections = [
        Detection(0.0, "actor_2", 0.5, 0.8, 0.9),
        Detection(0.0, "actor_1", 0.2, 0.7, 0.8),
        Detection(0.5, "actor_1", 0.25, 0.7, 0.85),
    ]
    points = BlockingTracker().build(detections)
    assert isinstance(points[0], BlockingPointIn)
    assert [p.actor for p in points] == ["actor_1", "actor_1", "actor_2"]
    assert [p.frame_ts for p in points[:2]] == [0.0, 0.5]
