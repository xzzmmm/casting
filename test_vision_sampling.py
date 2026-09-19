# -*- coding: utf-8 -*-
"""验证视频全片均匀采样：合成 30 秒视频，断言抽帧覆盖开头到结尾且等间距。"""
import os
import sys

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from src.vision_processor import VisionProcessor  # noqa: E402

OUT_DIR = r"D:\CastingNuwa_test"
os.makedirs(OUT_DIR, exist_ok=True)
video_path = os.path.join(OUT_DIR, "synthetic_30s.mp4")

FPS = 30
DURATION = 30
TOTAL = FPS * DURATION  # 900 帧
W, H = 160, 120

writer = cv2.VideoWriter(video_path, cv2.VideoWriter_fourcc(*"mp4v"), FPS, (W, H))
for i in range(TOTAL):
    # 亮度随帧号变化，便于确认帧内容随时间不同
    value = int(255 * i / TOTAL)
    frame = np.full((H, W, 3), value, dtype=np.uint8)
    writer.write(frame)
writer.release()

processor = VisionProcessor(max_frames=30)
frames = processor.extract_frames(video_path)
ts = processor.frame_timestamps

print("duration =", round(processor.video_duration, 2), "秒")
print("采样帧数 =", len(ts))
print("首帧时间戳 =", round(ts[0], 3), " 末帧时间戳 =", round(ts[-1], 3))
print("sampling_note =", processor.sampling_note)

gaps = [ts[i + 1] - ts[i] for i in range(len(ts) - 1)]
assert processor.video_duration > 29.5, "视频时长应为约 30 秒"
assert ts[0] < 0.2, "首帧应贴近片头"
assert ts[-1] > processor.video_duration - 0.5, "末帧必须覆盖到片尾（旧逻辑只抽开头会失败）"
assert max(gaps) - min(gaps) < 0.3, "采样间隔应近似等距"
assert "全片均匀采样" in processor.sampling_note, "采样说明应标注全片均匀采样"

# 结果对象应携带时间戳与覆盖信息（供多模态/逐段核对）
result = processor.analyze_video(video_path)
assert len(result.frame_timestamps) == len(ts), "分析结果应保留逐帧时间戳"
assert result.duration > 29.5, "结果应携带总时长"
assert result.sampling_note, "结果应携带采样覆盖说明"

print("\n✅ 全片均匀采样与时间戳测试通过（开头到片尾均覆盖）")
