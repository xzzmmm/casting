"""
CastingNuwa · 选角女娲
视觉处理模块（Vision Processor）

功能：
1. 从视频中抽帧
2. MediaPipe 面部关键点检测（468个关键点）
3. 面部表情分析（基于关键点的几何特征：笑容幅度、眉部状态、眼部开合等）
4. 姿态检测（MediaPipe Pose，33个关键点）
5. 肢体语言分析（手势丰富度、姿态自然度、空间使用等）

输出：
- 面部表情特征字典
- 肢体/姿态特征字典
- 综合视觉分析结果
"""

import os
import json
import tempfile
from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Any, Tuple
import math


def fmt_ts(seconds: float) -> str:
    """把秒数格式化为 m:ss。"""
    try:
        total = int(round(float(seconds)))
    except (TypeError, ValueError):
        return "0:00"
    return f"{total // 60}:{total % 60:02d}"


@dataclass
class FacialExpressionFeatures:
    """面部表情特征"""
    # 基础统计
    frames_analyzed: int = 0              # 分析的帧数
    face_detected_ratio: float = 0.0      # 人脸检测率

    # 笑容特征
    smile_intensity_mean: float = 0.0     # 平均笑容幅度
    smile_intensity_std: float = 0.0      # 笑容幅度标准差
    smile_ratio: float = 0.0               # 有笑容的帧比例
    max_smile_intensity: float = 0.0       # 最大笑容幅度

    # 眼部特征
    eye_openness_mean: float = 0.0         # 平均眼睛开合度
    eye_openness_std: float = 0.0          # 眼睛开合度标准差
    blink_rate: float = 0.0                 # 眨眼频率（次/分钟）

    # 眉部特征
    brow_raise_mean: float = 0.0           # 平均眉毛抬升度
    brow_furrow_mean: float = 0.0          # 平均眉毛皱眉度

    # 表情丰富度
    expression_range: float = 0.0           # 表情变化范围（丰富度）
    expression_variation: float = 0.0       # 表情变化量
    micro_expression_count: int = 0          # 微表情次数估计

    # 综合评估
    expression_category: str = ""            # 表情分类（丰富/适中/内敛/木讷）
    eye_contact_category: str = ""           # 眼神传达分类
    facial_strengths: List[str] = field(default_factory=list)
    facial_limitations: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    def summary(self) -> str:
        lines = [
            f"=== 面部表情分析 ===",
            f"分析帧数：{self.frames_analyzed} | 人脸检测率：{self.face_detected_ratio:.1%}",
            f"",
            f"【笑容】",
            f"  平均幅度：{self.smile_intensity_mean:.3f} | 笑容帧比例：{self.smile_ratio:.1%}",
            f"  最大幅度：{self.max_smile_intensity:.3f}",
            f"",
            f"【眼部】",
            f"  平均开合度：{self.eye_openness_mean:.3f} | 眨眼频率：{self.blink_rate:.1f}次/分钟",
            f"",
            f"【眉部】",
            f"  抬升度：{self.brow_raise_mean:.3f} | 皱眉度：{self.brow_furrow_mean:.3f}",
            f"",
            f"【表情丰富度】",
            f"  变化范围：{self.expression_range:.3f} | 变化量：{self.expression_variation:.3f}",
            f"  分类：{self.expression_category}",
            f"  眼神传达：{self.eye_contact_category}",
            f"",
            f"【优势】{', '.join(self.facial_strengths) if self.facial_strengths else '无'}",
            f"【局限】{', '.join(self.facial_limitations) if self.facial_limitations else '无'}",
        ]
        return "\n".join(lines)


@dataclass
class BodyLanguageFeatures:
    """肢体语言特征"""
    # 基础统计
    frames_analyzed: int = 0
    pose_detected_ratio: float = 0.0

    # 手势/手臂特征
    hand_movement_mean: float = 0.0        # 手部平均移动幅度
    hand_movement_std: float = 0.0         # 手部移动幅度标准差
    gesture_ratio: float = 0.0              # 有手势的帧比例
    arm_extension_mean: float = 0.0         # 手臂伸展度

    # 姿态特征
    posture_straightness: float = 0.0       # 姿态挺拔度
    posture_variation: float = 0.0           # 姿态变化量
    head_movement_mean: float = 0.0          # 头部移动幅度
    head_tilt_mean: float = 0.0              # 头部倾斜度

    # 空间使用
    spatial_usage_width: float = 0.0         # 水平空间使用范围
    spatial_usage_depth: float = 0.0         # 深度空间使用范围
    movement_flow: float = 0.0                # 移动流畅度

    # 综合评估
    gesture_category: str = ""                # 手势分类（丰富/适中/保守/僵硬）
    posture_category: str = ""                # 姿态分类（挺拔/自然/懒散/僵硬）
    spatial_category: str = ""                # 空间使用分类（主动/适中/保守）
    body_strengths: List[str] = field(default_factory=list)
    body_limitations: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    def summary(self) -> str:
        lines = [
            f"=== 肢体语言分析 ===",
            f"分析帧数：{self.frames_analyzed} | 姿态检测率：{self.pose_detected_ratio:.1%}",
            f"",
            f"【手势/手臂】",
            f"  平均移动幅度：{self.hand_movement_mean:.3f} | 手势帧比例：{self.gesture_ratio:.1%}",
            f"  手臂伸展度：{self.arm_extension_mean:.3f}",
            f"  分类：{self.gesture_category}",
            f"",
            f"【姿态】",
            f"  挺拔度：{self.posture_straightness:.3f} | 变化量：{self.posture_variation:.3f}",
            f"  头部移动：{self.head_movement_mean:.3f} | 头部倾斜：{self.head_tilt_mean:.3f}",
            f"  分类：{self.posture_category}",
            f"",
            f"【空间使用】",
            f"  水平范围：{self.spatial_usage_width:.3f} | 深度范围：{self.spatial_usage_depth:.3f}",
            f"  移动流畅度：{self.movement_flow:.3f}",
            f"  分类：{self.spatial_category}",
            f"",
            f"【优势】{', '.join(self.body_strengths) if self.body_strengths else '无'}",
            f"【局限】{', '.join(self.body_limitations) if self.body_limitations else '无'}",
        ]
        return "\n".join(lines)


@dataclass
class VisionAnalysisResult:
    """视觉分析完整结果"""
    facial_features: FacialExpressionFeatures = field(default_factory=FacialExpressionFeatures)
    body_features: BodyLanguageFeatures = field(default_factory=BodyLanguageFeatures)
    frames_extracted: int = 0
    video_path: str = ""
    analysis_sources: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    frame_timestamps: List[float] = field(default_factory=list)  # 每帧对应的时间点（秒）
    duration: float = 0.0        # 视频总时长（秒）
    sampling_note: str = ""      # 采样覆盖区间的人类可读说明

    def to_dict(self) -> dict:
        return {
            "facial_features": self.facial_features.to_dict(),
            "body_features": self.body_features.to_dict(),
            "frames_extracted": self.frames_extracted,
            "video_path": self.video_path,
            "analysis_sources": self.analysis_sources,
            "warnings": self.warnings,
            "frame_timestamps": self.frame_timestamps,
            "duration": self.duration,
            "sampling_note": self.sampling_note,
        }


class VisionProcessor:
    """视觉处理器"""

    def __init__(
        self,
        max_frames: int = 30,
        frame_interval: float = 0.5,
        min_detection_confidence: float = 0.5,
        min_tracking_confidence: float = 0.5,
    ):
        """
        初始化视觉处理器

        Args:
            max_frames: 最大分析帧数
            frame_interval: 抽帧间隔（秒）
            min_detection_confidence: 最小检测置信度
            min_tracking_confidence: 最小跟踪置信度
        """
        self.max_frames = max_frames
        self.frame_interval = frame_interval
        self.min_detection_confidence = min_detection_confidence
        self.min_tracking_confidence = min_tracking_confidence

        self._face_mesh = None
        self._pose = None
        self._cv2_available = False
        self._mediapipe_available = False

        # 检查依赖
        try:
            import cv2
            self._cv2_available = True
        except ImportError:
            pass

        try:
            import mediapipe as mp
            # mediapipe 1.0+ / Python 3.13 构建移除了 solutions API
            if hasattr(mp, 'solutions'):
                self._mediapipe_available = True
            else:
                self._mediapipe_available = False
                print("  ⚠️  mediapipe 已安装但无 solutions API（版本过新或 Python 3.13 构建），视觉分析将跳过")
        except ImportError:
            pass

    def _init_face_mesh(self):
        """初始化 Face Mesh"""
        if self._face_mesh is None:
            if not self._mediapipe_available:
                raise ImportError("mediapipe 未安装")
            import mediapipe as mp
            self._face_mesh = mp.solutions.face_mesh.FaceMesh(
                static_image_mode=False,
                max_num_faces=1,
                refine_landmarks=True,
                min_detection_confidence=self.min_detection_confidence,
                min_tracking_confidence=self.min_tracking_confidence,
            )
        return self._face_mesh

    def _init_pose(self):
        """初始化 Pose"""
        if self._pose is None:
            if not self._mediapipe_available:
                raise ImportError("mediapipe 未安装")
            import mediapipe as mp
            self._pose = mp.solutions.pose.Pose(
                static_image_mode=False,
                model_complexity=1,
                smooth_landmarks=True,
                min_detection_confidence=self.min_detection_confidence,
                min_tracking_confidence=self.min_tracking_confidence,
            )
        return self._pose

    def extract_frames(self, video_path: str) -> List:
        """
        从视频中抽帧

        Args:
            video_path: 视频文件路径

        Returns:
            帧列表（RGB 格式）
        """
        if not self._cv2_available:
            raise ImportError("opencv-python 未安装，请运行: pip install opencv-python")

        import cv2
        import numpy as np

        print(f"  [VisionProcessor] 从视频抽帧: {video_path}")

        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise ValueError(f"无法打开视频文件: {video_path}")

        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = total_frames / fps if fps > 0 else 0

        # 全片均匀采样：在 [0, 末帧] 等距取点，覆盖开头到结尾，
        # 避免旧逻辑“从头按固定间隔取前 N 帧”导致长视频后半段完全丢失。
        if total_frames > 0:
            target = min(self.max_frames, total_frames)
            if target <= 1:
                frame_indices = [0]
            else:
                raw_indices = np.linspace(0, total_frames - 1, target)
                frame_indices = sorted({int(x) for x in raw_indices})
        else:
            frame_indices = []

        frames = []
        timestamps = []
        for idx in frame_indices:
            cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
            ret, frame = cap.read()
            if ret:
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                frames.append(frame_rgb)
                timestamps.append(idx / fps if fps > 0 else 0.0)

        cap.release()
        self.frame_timestamps = timestamps
        self.video_duration = duration
        if timestamps:
            cover = f"{fmt_ts(timestamps[0])}-{fmt_ts(timestamps[-1])}"
            self.sampling_note = (
                f"全片均匀采样 {len(timestamps)} 帧，覆盖 {cover}，总时长 {duration:.1f} 秒"
            )
            print(
                f"  [VisionProcessor] 均匀抽取 {len(frames)} 帧，覆盖 {cover}"
                f"（总时长 {duration:.1f} 秒，FPS {fps:.1f}）"
            )
        else:
            self.sampling_note = ""
            print("  [VisionProcessor] 未能抽取到有效帧")
        return frames

    def _calculate_distance(self, point1, point2) -> float:
        """计算两个关键点之间的欧氏距离"""
        return math.sqrt(
            (point1.x - point2.x) ** 2 +
            (point1.y - point2.y) ** 2 +
            (getattr(point1, 'z', 0) - getattr(point2, 'z', 0)) ** 2
        )

    def analyze_facial_expression(self, frames: List) -> FacialExpressionFeatures:
        """
        分析面部表情

        Args:
            frames: 帧列表（RGB）

        Returns:
            面部表情特征
        """
        import numpy as np

        features = FacialExpressionFeatures()
        features.frames_analyzed = len(frames)

        if not self._mediapipe_available or len(frames) == 0:
            return features

        face_mesh = self._init_face_mesh()

        smile_intensities = []
        eye_openness_list = []
        brow_raise_list = []
        brow_furrow_list = []
        face_detected_count = 0
        blink_count = 0
        prev_eye_openness = None

        for frame in frames:
            results = face_mesh.process(frame)

            if not results.multi_face_landmarks:
                continue

            face_detected_count += 1
            landmarks = results.multi_face_landmarks[0].landmark

            # 笑容幅度（嘴角距离 vs 面部宽度）
            left_mouth = landmarks[61]
            right_mouth = landmarks[291]
            left_cheek = landmarks[234]
            right_cheek = landmarks[454]

            mouth_width = self._calculate_distance(left_mouth, right_mouth)
            face_width = self._calculate_distance(left_cheek, right_cheek)
            smile_intensity = mouth_width / (face_width + 1e-6)
            smile_intensities.append(smile_intensity)

            # 眼睛开合度（上下眼睑距离）
            left_eye_top = landmarks[159]
            left_eye_bottom = landmarks[145]
            right_eye_top = landmarks[386]
            right_eye_bottom = landmarks[374]

            left_eye_open = self._calculate_distance(left_eye_top, left_eye_bottom)
            right_eye_open = self._calculate_distance(right_eye_top, right_eye_bottom)
            eye_openness = (left_eye_open + right_eye_open) / 2
            eye_openness_list.append(eye_openness)

            # 眨眼检测
            if prev_eye_openness is not None and eye_openness < prev_eye_openness * 0.5:
                blink_count += 1
            prev_eye_openness = eye_openness

            # 眉毛抬升（眉毛到眼睛的距离）
            left_brow = landmarks[105]
            right_brow = landmarks[334]
            left_eye = landmarks[159]
            right_eye = landmarks[386]

            brow_raise = (
                self._calculate_distance(left_brow, left_eye) +
                self._calculate_distance(right_brow, right_eye)
            ) / 2
            brow_raise_list.append(brow_raise)

            # 皱眉（两眉之间距离）
            left_brow_inner = landmarks[70]
            right_brow_inner = landmarks[300]
            brow_furrow = 1.0 - (self._calculate_distance(left_brow_inner, right_brow_inner) / (face_width + 1e-6))
            brow_furrow_list.append(max(0, brow_furrow))

        # 统计特征
        if face_detected_count > 0:
            features.face_detected_ratio = face_detected_count / len(frames)

            if smile_intensities:
                features.smile_intensity_mean = float(np.mean(smile_intensities))
                features.smile_intensity_std = float(np.std(smile_intensities))
                features.max_smile_intensity = float(np.max(smile_intensities))
                features.smile_ratio = sum(1 for s in smile_intensities if s > 0.45) / len(smile_intensities)

            if eye_openness_list:
                features.eye_openness_mean = float(np.mean(eye_openness_list))
                features.eye_openness_std = float(np.std(eye_openness_list))
                duration_approx = len(frames) * self.frame_interval
                features.blink_rate = (blink_count / duration_approx) * 60 if duration_approx > 0 else 0

            if brow_raise_list:
                features.brow_raise_mean = float(np.mean(brow_raise_list))

            if brow_furrow_list:
                features.brow_furrow_mean = float(np.mean(brow_furrow_list))

            # 表情丰富度
            all_features = smile_intensities + eye_openness_list + brow_raise_list
            if all_features:
                features.expression_range = float(np.max(all_features) - np.min(all_features))
                features.expression_variation = float(np.std(all_features))

            # 微表情估计（快速变化的次数）
            if len(smile_intensities) > 2:
                for i in range(1, len(smile_intensities) - 1):
                    if abs(smile_intensities[i] - smile_intensities[i-1]) > 0.05 and \
                       abs(smile_intensities[i+1] - smile_intensities[i]) > 0.05:
                        features.micro_expression_count += 1

        # 分类评估
        features = self._classify_facial_features(features)

        print(f"  [VisionProcessor] 面部表情分析完成 (检测率: {features.face_detected_ratio:.1%})")
        return features

    def _classify_facial_features(self, features: FacialExpressionFeatures) -> FacialExpressionFeatures:
        """面部表情分类评估"""
        # 表情丰富度分类
        if features.expression_variation > 0.05:
            features.expression_category = "丰富（表情变化大，表现力强）"
            features.facial_strengths.append("表情丰富，表现力强")
        elif features.expression_variation > 0.02:
            features.expression_category = "适中（表情自然，有一定变化）"
        else:
            features.expression_category = "内敛/木讷（表情变化小，偏内敛）"
            features.facial_limitations.append("表情变化较小，需要加强面部表现力")

        # 眼神传达分类
        if features.eye_openness_mean > 0.02 and features.eye_openness_std > 0.005:
            features.eye_contact_category = "眼神有戏，开合度变化大，能传达复杂情感"
            features.facial_strengths.append("眼神传达力强，微表情细腻")
        elif features.eye_openness_mean > 0.015:
            features.eye_contact_category = "眼神自然，有一定传达力"
        else:
            features.eye_contact_category = "眼神偏平，需要加强眼部表达"
            features.facial_limitations.append("眼神表达偏弱")

        # 笑容评估
        if features.smile_ratio > 0.5:
            features.facial_strengths.append("笑容自然，亲和力强")
        elif features.smile_ratio < 0.1 and features.max_smile_intensity > 0.4:
            features.facial_strengths.append("笑容有爆发力，适合情绪转折场景")

        return features

    def analyze_body_language(self, frames: List) -> BodyLanguageFeatures:
        """
        分析肢体语言

        Args:
            frames: 帧列表（RGB）

        Returns:
            肢体语言特征
        """
        import numpy as np

        features = BodyLanguageFeatures()
        features.frames_analyzed = len(frames)

        if not self._mediapipe_available or len(frames) == 0:
            return features

        pose = self._init_pose()

        hand_positions = []
        shoulder_positions = []
        head_positions = []
        hip_positions = []
        pose_detected_count = 0

        for frame in frames:
            results = pose.process(frame)

            if not results.pose_landmarks:
                continue

            pose_detected_count += 1
            landmarks = results.pose_landmarks.landmark

            # 关键点索引（MediaPipe Pose）
            # 0: nose, 11: left_shoulder, 12: right_shoulder
            # 13: left_elbow, 14: right_elbow, 15: left_wrist, 16: right_wrist
            # 23: left_hip, 24: right_hip

            left_wrist = landmarks[15]
            right_wrist = landmarks[16]
            left_shoulder = landmarks[11]
            right_shoulder = landmarks[12]
            nose = landmarks[0]
            left_hip = landmarks[23]
            right_hip = landmarks[24]

            hand_positions.append((
                (left_wrist.x + right_wrist.x) / 2,
                (left_wrist.y + right_wrist.y) / 2,
            ))
            shoulder_positions.append((
                (left_shoulder.x + right_shoulder.x) / 2,
                (left_shoulder.y + right_shoulder.y) / 2,
            ))
            head_positions.append((nose.x, nose.y))
            hip_positions.append((
                (left_hip.x + right_hip.x) / 2,
                (left_hip.y + right_hip.y) / 2,
            ))

            # 手臂伸展度
            left_arm_length = self._calculate_distance(left_shoulder, left_wrist)
            right_arm_length = self._calculate_distance(right_shoulder, right_wrist)
            shoulder_width = self._calculate_distance(left_shoulder, right_shoulder)
            arm_extension = (left_arm_length + right_arm_length) / (2 * shoulder_width + 1e-6)
            features.arm_extension_mean += arm_extension

        if pose_detected_count > 0:
            features.pose_detected_ratio = pose_detected_count / len(frames)
            features.arm_extension_mean /= pose_detected_count

            # 手部移动幅度
            if len(hand_positions) > 1:
                movements = []
                for i in range(1, len(hand_positions)):
                    dx = hand_positions[i][0] - hand_positions[i-1][0]
                    dy = hand_positions[i][1] - hand_positions[i-1][1]
                    movements.append(math.sqrt(dx*dx + dy*dy))
                features.hand_movement_mean = float(np.mean(movements))
                features.hand_movement_std = float(np.std(movements))
                features.gesture_ratio = sum(1 for m in movements if m > 0.02) / len(movements)

            # 姿态挺拔度（肩到髋的垂直距离）
            if shoulder_positions and hip_positions:
                straightness = []
                for i in range(min(len(shoulder_positions), len(hip_positions))):
                    vertical_dist = abs(shoulder_positions[i][1] - hip_positions[i][1])
                    horizontal_dist = abs(shoulder_positions[i][0] - hip_positions[i][0])
                    straightness.append(vertical_dist / (vertical_dist + horizontal_dist + 1e-6))
                features.posture_straightness = float(np.mean(straightness))
                features.posture_variation = float(np.std(straightness))

            # 头部移动
            if len(head_positions) > 1:
                head_moves = []
                head_tilts = []
                for i in range(1, len(head_positions)):
                    dx = head_positions[i][0] - head_positions[i-1][0]
                    dy = head_positions[i][1] - head_positions[i-1][1]
                    head_moves.append(math.sqrt(dx*dx + dy*dy))
                    head_tilts.append(abs(dx))
                features.head_movement_mean = float(np.mean(head_moves))
                features.head_tilt_mean = float(np.mean(head_tilts))

            # 空间使用
            if hand_positions:
                xs = [p[0] for p in hand_positions]
                ys = [p[1] for p in hand_positions]
                features.spatial_usage_width = max(xs) - min(xs)
                features.spatial_usage_depth = max(ys) - min(ys)

            # 移动流畅度（基于移动幅度的标准差，越小越流畅）
            if features.hand_movement_std > 0:
                features.movement_flow = 1.0 / (1.0 + features.hand_movement_std * 10)

        # 分类评估
        features = self._classify_body_features(features)

        print(f"  [VisionProcessor] 肢体语言分析完成 (检测率: {features.pose_detected_ratio:.1%})")
        return features

    def _classify_body_features(self, features: BodyLanguageFeatures) -> BodyLanguageFeatures:
        """肢体语言分类评估"""
        # 手势分类
        if features.gesture_ratio > 0.5:
            features.gesture_category = "丰富（手势多，表达力强）"
            features.body_strengths.append("手势丰富，表达力强")
        elif features.gesture_ratio > 0.3:
            features.gesture_category = "适中（手势自然，不过度）"
        else:
            features.gesture_category = "保守/僵硬（手势少，偏拘谨）"
            features.body_limitations.append("手势偏少，需要加强肢体表达")

        # 姿态分类
        if features.posture_straightness > 0.8:
            features.posture_category = "挺拔（姿态端正，有气场）"
            features.body_strengths.append("姿态挺拔，有领导者气场")
        elif features.posture_straightness > 0.6:
            features.posture_category = "自然（姿态放松自然）"
        else:
            features.posture_category = "懒散/僵硬（姿态不够端正）"
            features.body_limitations.append("姿态不够端正，需要加强形体训练")

        # 空间使用分类
        if features.spatial_usage_width > 0.3:
            features.spatial_category = "主动（空间使用充分，舞台感强）"
            features.body_strengths.append("空间使用主动，舞台感强")
        elif features.spatial_usage_width > 0.15:
            features.spatial_category = "适中（空间使用合理）"
        else:
            features.spatial_category = "保守（空间使用偏局限）"
            features.body_limitations.append("空间使用偏保守，需要更主动地使用舞台空间")

        return features

    def analyze_video(self, video_path: str) -> VisionAnalysisResult:
        """
        完整视频视觉分析：面部表情 + 肢体语言

        Args:
            video_path: 视频文件路径

        Returns:
            视觉分析结果
        """
        result = VisionAnalysisResult()
        result.video_path = video_path
        result.analysis_sources.append("video")

        # 抽帧（全片均匀采样，带时间戳）
        frames = self.extract_frames(video_path)
        result.frames_extracted = len(frames)
        result.frame_timestamps = list(getattr(self, "frame_timestamps", []))
        result.duration = getattr(self, "video_duration", 0.0)
        result.sampling_note = getattr(self, "sampling_note", "")

        if len(frames) == 0:
            return result

        # mediapipe 不可用时跳过视觉分析（优雅降级，但保留全片采样覆盖信息）
        if not self._mediapipe_available:
            result.warnings.append("mediapipe solutions API 不可用，已跳过高阶视觉分析（面部表情/肢体语言）")
            if result.sampling_note:
                result.warnings.append(result.sampling_note + "；帧时间戳已保留，供逐段核对")
            print("  ⚠️  mediapipe solutions 不可用，跳过面部/肢体分析，仅保留基础帧信息")
            return result

        # 面部表情分析
        result.facial_features = self.analyze_facial_expression(frames)

        # 肢体语言分析
        result.body_features = self.analyze_body_language(frames)

        return result

    def close(self):
        """释放资源"""
        if self._face_mesh:
            self._face_mesh.close()
            self._face_mesh = None
        if self._pose:
            self._pose.close()
            self._pose = None
