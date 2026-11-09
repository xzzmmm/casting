"""语音转写服务：SenseVoice + fsmn-vad 本地推理（W3 已接入，链路经 W1 验证）。"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

_LANGUAGE_TAG = re.compile(r"<\|[^|>]+\|>")
_DEFAULT_MODEL = "iic/SenseVoiceSmall"


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
class TranscriptionSegment:
    start: float
    end: float
    text: str


class Transcriber(ABC):
    """语音转写抽象接口。"""

    @abstractmethod
    def transcribe(self, media_path: Path) -> list[TranscriptionSegment]:
        """将音频轨转为带时间戳的文本片段。"""


class SenseVoiceTranscriber(Transcriber):
    """基于 FunASR / SenseVoice 的本地实现。

    模型按需懒加载并缓存为类级单例，多次排练只加载一次。
    输出文本会去除 SenseVoice 自带的 <|zh|> 等语言/情感标签。
    """

    _model = None

    def __init__(self, device: str = "auto", model_name: str = _DEFAULT_MODEL):
        self._device = device
        self._model_name = model_name

    def _load_model(self):
        if SenseVoiceTranscriber._model is None:
            from funasr import AutoModel

            SenseVoiceTranscriber._model = AutoModel(
                model=self._model_name,
                vad_model="fsmn-vad",
                vad_kwargs={"max_single_segment_time": 30000},
                device=_pick_device(self._device),
                disable_update=True,
            )
        return SenseVoiceTranscriber._model

    @staticmethod
    def clean_text(text: str) -> str:
        """去除 SenseVoice 的语言/情感/事件标签（<|zh|> 等）。"""
        return _LANGUAGE_TAG.sub("", text).strip()

    def transcribe(self, media_path: Path) -> list[TranscriptionSegment]:
        model = self._load_model()
        result = model.generate(
            input=str(media_path),
            return_raw_text=False,
            is_final=True,
            language="auto",
            enable_itn=True,
            output_timestamp=True,
        )
        entry = result[0]
        text = self.clean_text(entry.get("text") or "")
        timestamps = entry.get("timestamp") or []
        words = entry.get("words") or []

        words_ts = [
            (ts[0] / 1000, ts[1] / 1000)
            for ts, _word in zip(timestamps, words)
        ]
        if not text or not words_ts:
            return []

        start = words_ts[0][0]
        end = words_ts[-1][1]
        return [TranscriptionSegment(start=start, end=end, text=text)]
