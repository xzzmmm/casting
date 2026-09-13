"""
CastingNuwa · 选角女娲
语音处理模块（Audio Processor）

功能：
1. 从视频文件中提取音频
2. Whisper 语音转写（faster-whisper，支持本地模型和 API）
3. 声学特征提取（librosa：音高、能量、语速、节奏、情感相关特征）

输出：
- 转写文本
- 声学特征字典（用于演员画像的声线特质分析）
"""

import os
import json
import tempfile
from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Any, Tuple


@dataclass
class AcousticFeatures:
    """声学特征"""
    # 基础特征
    duration: float = 0.0               # 音频时长（秒）
    sample_rate: int = 0                 # 采样率

    # 音高特征
    pitch_mean: float = 0.0              # 平均音高（Hz）
    pitch_std: float = 0.0               # 音高标准差
    pitch_min: float = 0.0               # 最低音高
    pitch_max: float = 0.0               # 最高音高
    pitch_range: float = 0.0             # 音高范围

    # 能量/响度特征
    rms_mean: float = 0.0                # 平均 RMS 能量
    rms_std: float = 0.0                 # RMS 标准差
    rms_max: float = 0.0                  # 最大 RMS

    # 语速/节奏特征
    speech_rate: float = 0.0             # 语速（字/分钟）
    syllable_rate: float = 0.0           # 音节速率
    pause_count: int = 0                  # 停顿次数
    pause_duration_mean: float = 0.0      # 平均停顿时长
    articulation_rate: float = 0.0        # 发音速率（纯发音时间）

    # 频谱特征
    spectral_centroid_mean: float = 0.0   # 频谱质心均值（音色亮度）
    spectral_centroid_std: float = 0.0    # 频谱质心标准差
    spectral_bandwidth_mean: float = 0.0   # 频谱带宽
    spectral_rolloff_mean: float = 0.0     # 频谱滚降点

    # 韵律/情感相关特征
    f0_variation: float = 0.0             # F0 变化量（韵律丰富度）
    energy_variation: float = 0.0          # 能量变化量
    jitter: float = 0.0                    # 基频微扰（声音稳定性）
    shimmer: float = 0.0                   # 振幅微扰

    # 综合评估
    pitch_category: str = ""               # 音高分类（高亢/中音/低沉）
    timbre_category: str = ""              # 音色分类（清亮/沙哑/磁性/温润）
    pace_category: str = ""                # 语速分类（快/适中/慢）
    emotion_expression: str = ""           # 情感表达能力评估
    vocal_strengths: List[str] = field(default_factory=list)
    vocal_limitations: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    def summary(self) -> str:
        """生成声学特征摘要"""
        lines = [
            f"=== 声学特征分析 ===",
            f"时长：{self.duration:.1f}秒 | 采样率：{self.sample_rate}Hz",
            f"",
            f"【音高】",
            f"  平均：{self.pitch_mean:.1f}Hz | 范围：{self.pitch_min:.0f}-{self.pitch_max:.0f}Hz",
            f"  分类：{self.pitch_category}",
            f"",
            f"【能量/响度】",
            f"  平均RMS：{self.rms_mean:.4f} | 最大：{self.rms_max:.4f}",
            f"",
            f"【语速/节奏】",
            f"  语速：{self.speech_rate:.0f}字/分钟 | 分类：{self.pace_category}",
            f"  停顿：{self.pause_count}次 | 平均停顿：{self.pause_duration_mean:.2f}秒",
            f"",
            f"【音色】",
            f"  频谱质心：{self.spectral_centroid_mean:.0f}Hz | 分类：{self.timbre_category}",
            f"",
            f"【韵律/情感】",
            f"  F0变化量：{self.f0_variation:.2f} | 能量变化：{self.energy_variation:.4f}",
            f"  情感表达：{self.emotion_expression}",
            f"",
            f"【声线优势】{', '.join(self.vocal_strengths) if self.vocal_strengths else '无'}",
            f"【声线局限】{', '.join(self.vocal_limitations) if self.vocal_limitations else '无'}",
        ]
        return "\n".join(lines)


@dataclass
class AudioAnalysisResult:
    """语音分析完整结果"""
    transcript: str = ""                   # 转写文本
    word_count: int = 0                    # 字数
    acoustic_features: AcousticFeatures = field(default_factory=AcousticFeatures)
    audio_path: str = ""                   # 音频文件路径
    analysis_sources: List[str] = field(default_factory=list)  # 分析来源

    def to_dict(self) -> dict:
        return {
            "transcript": self.transcript,
            "word_count": self.word_count,
            "acoustic_features": self.acoustic_features.to_dict(),
            "audio_path": self.audio_path,
            "analysis_sources": self.analysis_sources,
        }


class AudioProcessor:
    """语音处理器"""

    def __init__(
        self,
        whisper_model_size: str = "base",
        device: str = "auto",
        compute_type: str = "auto",
    ):
        """
        初始化语音处理器

        Args:
            whisper_model_size: Whisper 模型大小（tiny/base/small/medium/large-v3）
            device: 计算设备（auto/cpu/cuda）
            compute_type: 计算类型（auto/int8/float16等）
        """
        self.whisper_model_size = whisper_model_size
        self.device = device
        self.compute_type = compute_type
        self._whisper_model = None
        self._librosa_available = False
        self._faster_whisper_available = False

        # 检查依赖
        try:
            import librosa
            self._librosa_available = True
        except ImportError:
            pass

        try:
            from faster_whisper import WhisperModel
            self._faster_whisper_available = True
        except ImportError:
            pass

    def _load_whisper_model(self):
        """懒加载 Whisper 模型"""
        if self._whisper_model is None:
            if not self._faster_whisper_available:
                raise ImportError("faster-whisper 未安装，请运行: pip install faster-whisper")

            from faster_whisper import WhisperModel

            device = self.device
            if device == "auto":
                try:
                    import torch
                    device = "cuda" if torch.cuda.is_available() else "cpu"
                except ImportError:
                    device = "cpu"

            compute_type = self.compute_type
            if compute_type == "auto":
                compute_type = "int8" if device == "cpu" else "float16"

            print(f"  [AudioProcessor] 加载 Whisper 模型 ({self.whisper_model_size}, {device}/{compute_type})...")
            self._whisper_model = WhisperModel(
                self.whisper_model_size,
                device=device,
                compute_type=compute_type,
            )
            print(f"  [AudioProcessor] Whisper 模型加载完成")

        return self._whisper_model

    def extract_audio_from_video(self, video_path: str, output_path: Optional[str] = None) -> str:
        """
        从视频文件中提取音频

        Args:
            video_path: 视频文件路径
            output_path: 输出音频路径（默认临时文件）

        Returns:
            音频文件路径
        """
        if output_path is None:
            output_path = os.path.join(tempfile.gettempdir(), f"extracted_audio_{os.getpid()}.wav")

        try:
            from moviepy.editor import VideoFileClip
            video = VideoFileClip(video_path)
            audio = video.audio
            if audio is not None:
                audio.write_audiofile(output_path, codec="pcm_s16le", logger=None)
            video.close()
            print(f"  [AudioProcessor] 音频提取完成: {output_path}")
            return output_path
        except ImportError:
            raise ImportError("moviepy 未安装，请运行: pip install moviepy")

    def transcribe(self, audio_path: str, language: str = "zh") -> Tuple[str, List[Dict]]:
        """
        语音转写

        Args:
            audio_path: 音频文件路径
            language: 语言代码（zh/en/auto）

        Returns:
            (转写文本, 分段信息列表)
        """
        model = self._load_whisper_model()

        print(f"  [AudioProcessor] 开始转写: {audio_path}")
        segments, info = model.transcribe(
            audio_path,
            language=language if language != "auto" else None,
            beam_size=5,
            vad_filter=True,
        )

        transcript_parts = []
        segment_list = []

        for segment in segments:
            transcript_parts.append(segment.text)
            segment_list.append({
                "start": segment.start,
                "end": segment.end,
                "text": segment.text,
                "avg_logprob": segment.avg_logprob,
            })

        transcript = "".join(transcript_parts).strip()
        print(f"  [AudioProcessor] 转写完成: {len(transcript)}字, {len(segment_list)}段")

        return transcript, segment_list

    def extract_acoustic_features(self, audio_path: str) -> AcousticFeatures:
        """
        提取声学特征

        Args:
            audio_path: 音频文件路径

        Returns:
            声学特征对象
        """
        if not self._librosa_available:
            raise ImportError("librosa 未安装，请运行: pip install librosa")

        import librosa
        import numpy as np

        print(f"  [AudioProcessor] 提取声学特征: {audio_path}")

        features = AcousticFeatures()

        # 加载音频
        y, sr = librosa.load(audio_path, sr=None, mono=True)
        features.sample_rate = sr
        features.duration = len(y) / sr

        if len(y) == 0:
            return features

        # 音高特征（F0）
        try:
            f0, voiced_flag, voiced_probs = librosa.pyin(
                y, fmin=librosa.note_to_hz('C2'), fmax=librosa.note_to_hz('C7')
            )
            f0_voiced = f0[voiced_flag & ~np.isnan(f0)]
            if len(f0_voiced) > 0:
                features.pitch_mean = float(np.mean(f0_voiced))
                features.pitch_std = float(np.std(f0_voiced))
                features.pitch_min = float(np.min(f0_voiced))
                features.pitch_max = float(np.max(f0_voiced))
                features.pitch_range = features.pitch_max - features.pitch_min
                features.f0_variation = float(np.std(f0_voiced) / (np.mean(f0_voiced) + 1e-6))
        except Exception as e:
            print(f"  [AudioProcessor] 音高提取警告: {e}")

        # RMS 能量
        try:
            rms = librosa.feature.rms(y=y)[0]
            features.rms_mean = float(np.mean(rms))
            features.rms_std = float(np.std(rms))
            features.rms_max = float(np.max(rms))
            features.energy_variation = float(np.std(rms) / (np.mean(rms) + 1e-6))
        except Exception as e:
            print(f"  [AudioProcessor] 能量提取警告: {e}")

        # 频谱特征
        try:
            spectral_centroid = librosa.feature.spectral_centroid(y=y, sr=sr)[0]
            features.spectral_centroid_mean = float(np.mean(spectral_centroid))
            features.spectral_centroid_std = float(np.std(spectral_centroid))

            spectral_bandwidth = librosa.feature.spectral_bandwidth(y=y, sr=sr)[0]
            features.spectral_bandwidth_mean = float(np.mean(spectral_bandwidth))

            spectral_rolloff = librosa.feature.spectral_rolloff(y=y, sr=sr)[0]
            features.spectral_rolloff_mean = float(np.mean(spectral_rolloff))
        except Exception as e:
            print(f"  [AudioProcessor] 频谱特征警告: {e}")

        # 语速估计（基于转写文本时长）
        # 这里先留空，由调用方传入转写文本后计算
        features.speech_rate = 0.0

        # 分类评估
        features = self._classify_acoustic_features(features)

        print(f"  [AudioProcessor] 声学特征提取完成")
        return features

    def _classify_acoustic_features(self, features: AcousticFeatures) -> AcousticFeatures:
        """基于数值特征进行分类和评估"""
        # 音高分类
        if features.pitch_mean > 0:
            if features.pitch_mean > 220:
                features.pitch_category = "高亢（女高音/男高音范围）"
            elif features.pitch_mean > 160:
                features.pitch_category = "中高音"
            elif features.pitch_mean > 110:
                features.pitch_category = "中音（最常见的人声范围）"
            else:
                features.pitch_category = "低沉（男低音/磁性低音范围）"

        # 音色分类（基于频谱质心）
        if features.spectral_centroid_mean > 0:
            if features.spectral_centroid_mean > 3000:
                features.timbre_category = "清亮明亮（高频丰富，穿透力强）"
            elif features.spectral_centroid_mean > 2000:
                features.timbre_category = "温润自然（平衡型音色）"
            elif features.spectral_centroid_mean > 1500:
                features.timbre_category = "柔和温暖（低频丰富）"
            else:
                features.timbre_category = "低沉磁性（厚重型音色）"

        # 韵律丰富度评估
        if features.f0_variation > 0.15:
            features.emotion_expression = "韵律丰富，情感表达能力强，音高变化大，适合表达复杂情感"
            features.vocal_strengths.append("韵律丰富，情感表达力强")
        elif features.f0_variation > 0.08:
            features.emotion_expression = "韵律适中，有一定情感表达能力"
        else:
            features.emotion_expression = "韵律较平，情感表达偏内敛，需要加强音高变化"
            features.vocal_limitations.append("韵律较平，情感表达偏内敛")

        # 声音稳定性
        if features.pitch_std > 0 and features.pitch_std < 30:
            features.vocal_strengths.append("音高稳定，声音控制好")
        elif features.pitch_std > 50:
            features.vocal_limitations.append("音高波动较大，声音稳定性需加强")

        return features

    def calculate_speech_rate(self, features: AcousticFeatures, word_count: int, duration: float) -> AcousticFeatures:
        """
        计算语速（需要转写文本和时长）

        Args:
            features: 声学特征对象
            word_count: 字数
            duration: 音频时长（秒）

        Returns:
            更新后的声学特征
        """
        if duration > 0:
            features.speech_rate = (word_count / duration) * 60  # 字/分钟

            if features.speech_rate > 280:
                features.pace_category = "快（语速快，适合紧张/激动场景）"
                features.vocal_strengths.append("语速快，表达流畅")
            elif features.speech_rate > 200:
                features.pace_category = "适中（自然语速，适合大多数场景）"
            elif features.speech_rate > 150:
                features.pace_category = "偏慢（语速较慢，适合沉稳/深情场景）"
            else:
                features.pace_category = "慢（语速很慢，适合严肃/悲伤场景）"
                features.vocal_limitations.append("语速偏慢，可能影响节奏紧凑的场景")

        return features

    def analyze(
        self,
        audio_path: str,
        language: str = "zh",
        extract_features: bool = True,
    ) -> AudioAnalysisResult:
        """
        完整语音分析：转写 + 声学特征

        Args:
            audio_path: 音频文件路径
            language: 语言
            extract_features: 是否提取声学特征

        Returns:
            语音分析结果
        """
        result = AudioAnalysisResult()
        result.audio_path = audio_path
        result.analysis_sources.append("audio")

        # 转写
        transcript, segments = self.transcribe(audio_path, language)
        result.transcript = transcript
        result.word_count = len(transcript)

        # 声学特征
        if extract_features:
            features = self.extract_acoustic_features(audio_path)
            features = self.calculate_speech_rate(features, result.word_count, features.duration)
            result.acoustic_features = features

        return result

    def analyze_video(
        self,
        video_path: str,
        language: str = "zh",
        extract_features: bool = True,
    ) -> AudioAnalysisResult:
        """
        从视频文件进行完整语音分析

        Args:
            video_path: 视频文件路径
            language: 语言
            extract_features: 是否提取声学特征

        Returns:
            语音分析结果
        """
        # 提取音频
        audio_path = self.extract_audio_from_video(video_path)

        # 分析
        result = self.analyze(audio_path, language, extract_features)
        result.analysis_sources.append("video")

        # 清理临时文件
        try:
            if os.path.exists(audio_path) and "temp" in audio_path.lower():
                os.remove(audio_path)
        except Exception:
            pass

        return result
