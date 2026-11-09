"""W1 技术验证：本地 ASR 转写链路（音频 → 带时间戳文本）。

用法：
    python scripts/asr_validate.py 音频路径 [--output 输出JSON路径] [--device auto|cpu|cuda:0]

示例：
    python scripts/asr_validate.py data/test_data/rehearsal_demo.wav --output data/test_data/asr_out.json

依赖（requirements-asr.txt）：
    建议先安装 CPU 版 PyTorch 以减小下载量：
        pip install torch torchaudio --index-url https://download.pytorch.org/whl/cpu
        pip install -r requirements-asr.txt

输出 JSON 结构（start/end 单位秒，可直接喂给模块 A 的 build_prompt）：
    {"model": "...", "elapsed_sec": 12.3, "segments": [{"start": 0.0, "end": 5.0, "text": "..."}]}
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

DEFAULT_MODEL = "iic/SenseVoiceSmall"
DEFAULT_VAD = "fsmn-vad"
DEFAULT_DEVICE = "auto"


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
    """加载 SenseVoiceSmall + VAD，首次运行会从 ModelScope 下载模型。"""
    from funasr import AutoModel

    return AutoModel(
        model=DEFAULT_MODEL,
        vad_model=DEFAULT_VAD,
        vad_kwargs={"max_single_segment_time": 30000},
        device=device,
        disable_update=True,
    )


def transcribe(model, audio_path: Path) -> dict:
    """转写并返回带时间戳的文本片段。

    返回 dict：
        segments: 句子级片段（start/end/text，秒），当前实现为整段合并。
        words:    词级时间戳（start/end/text，秒），供后续句子切分使用。
    """
    result = model.generate(
        input=str(audio_path),
        return_raw_text=False,
        is_final=True,
        language="auto",
        enable_itn=True,
        output_timestamp=True,
    )
    entry = result[0]
    text = entry.get("text") or ""
    timestamps = entry.get("timestamp") or []
    words = entry.get("words") or []

    words_ts = [
        {
            "start": ts[0] / 1000,
            "end": ts[1] / 1000,
            "text": word,
        }
        for ts, word in zip(timestamps, words)
    ]
    segments = []
    if text:
        start = words_ts[0]["start"] if words_ts else 0.0
        end = words_ts[-1]["end"] if words_ts else 0.0
        segments.append({"start": start, "end": end, "text": text})
    return {"segments": segments, "words": words_ts}


def run(audio_path: Path, output_path: Path | None, device: str) -> dict:
    print(f"[1/3] 加载模型：{DEFAULT_MODEL}（设备 {device}）")
    model = load_model(device)

    print(f"[2/3] 转写：{audio_path}")
    started = time.monotonic()
    result = transcribe(model, audio_path)
    elapsed = time.monotonic() - started
    segments = result["segments"]

    print(f"[3/3] 完成，用时 {elapsed:.1f} 秒，共 {len(segments)} 段")
    for seg in segments:
        print(f"  [{seg['start']:.1f} ~ {seg['end']:.1f}s] {seg['text']}")

    payload = {
        "model": DEFAULT_MODEL,
        "elapsed_sec": round(elapsed, 2),
        "segments": segments,
        "words": result["words"],
    }
    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"结果已保存：{output_path}")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="StageMind W1 ASR 转写验证")
    parser.add_argument("audio", type=Path, help="待转写音频路径")
    parser.add_argument("--output", type=Path, default=None, help="输出 JSON 路径")
    parser.add_argument(
        "--device", default=DEFAULT_DEVICE, help="auto / cpu / cuda:0"
    )
    args = parser.parse_args()

    if not args.audio.exists():
        print(f"音频不存在：{args.audio}", file=sys.stderr)
        return 1

    run(args.audio, args.output, pick_device(args.device))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
