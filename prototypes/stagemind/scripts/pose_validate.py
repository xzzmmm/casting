"""W2 技术验证：CV 台位检测链路（图片/视频 → 演员台位坐标）。

用法：
    python scripts/pose_validate.py 媒体路径 [--output 输出JSON路径] [--device auto|cpu|cuda:0]

示例：
    python scripts/pose_validate.py data/test_data/stage_demo.jpg --output data/test_data/pose_out.json

依赖（requirements-cv.txt）：
    pip install -r requirements-cv.txt

输出 JSON 结构（与 backend/app/services/pose.py 的 Detection 对齐，x/y 为归一化舞台坐标 0~1）：
    {
      "source": "...", "elapsed_sec": 0.8,
      "detections": [
        {"frame_ts": 0.0, "actor_id": "actor_1", "x": 0.42, "y": 0.87, "confidence": 0.93}
      ]
    }

说明：台位取人体检测框底部中心（人物站立的地面点）；actor_id 按画面从左到右编号；
视频默认每 0.5 秒抽一帧，最多处理 20 帧，用于验证链路而非完整动线跟踪。
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

DEFAULT_MODEL = "yolov8n-pose.pt"
DEFAULT_DEVICE = "auto"
FRAME_INTERVAL_SEC = 0.5
MAX_FRAMES = 20


def pick_device(preference: str) -> str:
    """auto 时按本机硬件选择；没有 torch 时回退 CPU。"""
    if preference != "auto":
        return preference
    try:
        import torch

        return "cuda:0" if torch.cuda.is_available() else "cpu"
    except ImportError:
        return "cpu"


def load_model(device: str):
    """加载 YOLOv8n-pose，首次运行自动下载权重（约 6MB）。"""
    from ultralytics import YOLO

    return YOLO(DEFAULT_MODEL).to(device)


def _collect_frames(media_path: Path) -> list[tuple[float, object]]:
    """返回 [(frame_ts, frame)] 列表；图片为单帧，视频按间隔抽帧。"""
    suffix = media_path.suffix.lower()
    if suffix in {".jpg", ".jpeg", ".png", ".bmp", ".webp"}:
        import cv2

        frame = cv2.imread(str(media_path))
        return [(0.0, frame)] if frame is not None else []

    import cv2

    capture = cv2.VideoCapture(str(media_path))
    if not capture.isOpened():
        return []
    fps = capture.get(cv2.CAP_PROP_FPS) or 25.0
    step = max(1, round(fps * FRAME_INTERVAL_SEC))
    frames: list[tuple[float, object]] = []
    index = 0
    while len(frames) < MAX_FRAMES:
        ok, frame = capture.read()
        if not ok:
            break
        if index % step == 0:
            frames.append((index / fps, frame))
        index += 1
    capture.release()
    return frames


def detect(model, media_path: Path) -> list[dict]:
    """检测每帧人体，输出归一化台位坐标（框底部中心）。"""
    frames = _collect_frames(media_path)
    detections: list[dict] = []
    for frame_ts, frame in frames:
        results = model.predict(frame, verbose=False, conf=0.3)
        boxes = results[0].boxes
        if boxes is None:
            continue
        height, width = frame.shape[:2]
        persons = []
        for box in boxes:
            if int(box.cls[0].item()) != 0:
                continue
            x1, y1, x2, y2 = (v.item() for v in box.xyxy[0])
            center_x = (x1 + x2) / 2 / width
            ground_y = y2 / height
            persons.append(
                {
                    "frame_ts": round(frame_ts, 2),
                    "x": round(center_x, 4),
                    "y": round(ground_y, 4),
                    "confidence": round(box.conf[0].item(), 4),
                }
            )
        persons.sort(key=lambda item: item["x"])
        for index, person in enumerate(persons, start=1):
            person["actor_id"] = f"actor_{index}"
            detections.append(person)
    return detections


def run(media_path: Path, output_path: Path | None, device: str) -> dict:
    print(f"[1/3] 加载模型：{DEFAULT_MODEL}（设备 {device}）")
    model = load_model(device)

    print(f"[2/3] 检测：{media_path}")
    started = time.monotonic()
    detections = detect(model, media_path)
    elapsed = time.monotonic() - started

    actors = sorted({item["actor_id"] for item in detections})
    print(f"[3/3] 完成，用时 {elapsed:.1f} 秒，检测到 {len(detections)} 个台位点（{len(actors)} 人）")
    for item in detections:
        print(
            f"  t={item['frame_ts']:.1f}s {item['actor_id']} "
            f"x={item['x']:.2f} y={item['y']:.2f} conf={item['confidence']:.2f}"
        )

    payload = {
        "model": DEFAULT_MODEL,
        "source": str(media_path),
        "elapsed_sec": round(elapsed, 2),
        "detections": detections,
    }
    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"结果已保存：{output_path}")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="StageMind W2 CV 台位检测验证")
    parser.add_argument("media", type=Path, help="图片或视频路径")
    parser.add_argument("--output", type=Path, default=None, help="输出 JSON 路径")
    parser.add_argument(
        "--device", default=DEFAULT_DEVICE, help="auto / cpu / cuda:0"
    )
    args = parser.parse_args()

    if not args.media.exists():
        print(f"媒体不存在：{args.media}", file=sys.stderr)
        return 1

    run(args.media, args.output, pick_device(args.device))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
