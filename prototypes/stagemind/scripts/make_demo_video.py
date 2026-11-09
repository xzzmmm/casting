"""生成 W2 视频动线验证用的合成演示素材。

从多人图片生成 3 秒 24fps 视频，模拟镜头水平摇移，使台位坐标逐帧变化，
用于验证多帧抽帧与动线输出链路。

用法：
    python scripts/make_demo_video.py [--source 图片路径] [--output 输出路径]
"""

from __future__ import annotations

import argparse
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC = PROJECT_ROOT / "data" / "test_data" / "stage_demo.jpg"
OUT = PROJECT_ROOT / "data" / "test_data" / "stage_demo_move.mp4"
FPS = 24
DURATION_SEC = 3
FRAME_WIDTH = 640
FRAME_HEIGHT = 480


def build_video(source: Path, output: Path) -> None:
    import cv2

    image = cv2.imread(str(source))
    if image is None:
        raise FileNotFoundError(f"素材不存在：{source}")

    # 整图缩放到目标画幅，保证人物完整入画，避免检测框贴边
    resized = cv2.resize(image, (FRAME_WIDTH, FRAME_HEIGHT))

    writer = cv2.VideoWriter(
        str(output),
        cv2.VideoWriter_fourcc(*"mp4v"),
        FPS,
        (FRAME_WIDTH, FRAME_HEIGHT),
    )
    total = FPS * DURATION_SEC
    crop_width = int(FRAME_WIDTH * 0.8)
    max_shift = FRAME_WIDTH - crop_width

    for index in range(total):
        ratio = index / max(total - 1, 1)
        x0 = int(ratio * max_shift)
        frame = resized[:, x0 : x0 + crop_width]
        frame = cv2.resize(frame, (FRAME_WIDTH, FRAME_HEIGHT))
        writer.write(frame)
    writer.release()
    print(f"生成完成：{output}（{DURATION_SEC}s @ {FPS}fps，水平摇移模拟）")


def main() -> int:
    parser = argparse.ArgumentParser(description="生成 W2 合成演示视频")
    parser.add_argument("--source", type=Path, default=SRC, help="输入图片路径")
    parser.add_argument("--output", type=Path, default=OUT, help="输出视频路径")
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    build_video(args.source, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
