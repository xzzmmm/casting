"""多人姿态估计服务：YOLOv8n-pose 本地推理（W6 已提前接入，链路经 W2 验证）。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

_DEFAULT_MODEL = "yolov8n-pose.pt"
_DEFAULT_MIN_CONFIDENCE = 0.5
_FRAME_INTERVAL_SEC = 0.5
_MAX_FRAMES = 20


def _pick_device(preference: str) -> str:
    """auto 时按本机硬件选择；没有 torch 时回退 CPU。"""
    if preference != "auto":
        return preference
    try:
        import torch

        return "cuda:0" if torch.cuda.is_available() else "cpu"
    except ImportError:
        return "cpu"


@dataclass(frozen=True)
class Detection:
    frame_ts: float
    actor_id: str
    x: float
    y: float
    confidence: float


class PoseDetector(ABC):
    """姿态估计抽象接口。"""

    @abstractmethod
    def detect(self, media_path: Path) -> list[Detection]:
        """抽取关键帧并返回归一化舞台坐标（0 到 1）。"""


class YoloPoseDetector(PoseDetector):
    """基于 YOLOv8n-pose 的本地实现。

    台位取人体检测框底部中心（站立地面点），actor_id 按画面从左到右编号；
    低置信度点（默认 conf < 0.5）过滤；视频按固定间隔抽帧。
    """

    _model = None

    def __init__(
        self,
        device: str = "auto",
        model_name: str = _DEFAULT_MODEL,
        min_confidence: float = _DEFAULT_MIN_CONFIDENCE,
    ):
        self._device = device
        self._model_name = model_name
        self._min_confidence = min_confidence

    def _load_model(self):
        if YoloPoseDetector._model is None:
            from ultralytics import YOLO

            YoloPoseDetector._model = YOLO(self._model_name).to(
                _pick_device(self._device)
            )
        return YoloPoseDetector._model

    @staticmethod
    def _collect_frames(media_path: Path) -> list[tuple[float, object]]:
        """返回 [(frame_ts, frame)]；图片单帧，视频按间隔抽帧。"""
        import cv2

        suffix = media_path.suffix.lower()
        if suffix in {".jpg", ".jpeg", ".png", ".bmp", ".webp"}:
            frame = cv2.imread(str(media_path))
            return [(0.0, frame)] if frame is not None else []

        capture = cv2.VideoCapture(str(media_path))
        if not capture.isOpened():
            return []
        fps = capture.get(cv2.CAP_PROP_FPS) or 25.0
        step = max(1, round(fps * _FRAME_INTERVAL_SEC))
        frames: list[tuple[float, object]] = []
        index = 0
        while len(frames) < _MAX_FRAMES:
            ok, frame = capture.read()
            if not ok:
                break
            if index % step == 0:
                frames.append((index / fps, frame))
            index += 1
        capture.release()
        return frames

    def detect(self, media_path: Path) -> list[Detection]:
        model = self._load_model()
        detections: list[Detection] = []
        for frame_ts, frame in self._collect_frames(media_path):
            results = model.predict(frame, verbose=False, conf=self._min_confidence)
            boxes = results[0].boxes
            if boxes is None:
                continue
            height, width = frame.shape[:2]
            persons = []
            for box in boxes:
                if int(box.cls[0].item()) != 0:
                    continue
                x1, y1, x2, y2 = (v.item() for v in box.xyxy[0])
                persons.append(
                    {
                        "x": (x1 + x2) / 2 / width,
                        "y": y2 / height,
                        "confidence": box.conf[0].item(),
                    }
                )
            persons.sort(key=lambda item: item["x"])
            for index, person in enumerate(persons, start=1):
                detections.append(
                    Detection(
                        frame_ts=round(frame_ts, 2),
                        actor_id=f"actor_{index}",
                        x=round(person["x"], 4),
                        y=round(person["y"], 4),
                        confidence=round(person["confidence"], 4),
                    )
                )
        return detections
