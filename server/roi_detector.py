import numpy as np
from typing import Tuple, List, Dict, Any
import cv2


class ROIDetector:
    """
    感兴趣区域(ROI)检测器，用于识别视频帧中的重要区域
    基于鼠标位置和画面内容变化
    """

    def __init__(self,
                 frame_width: int,
                 frame_height: int,
                 roi_size: int = 200,
                 content_change_threshold: float = 0.05):
        """
        初始化ROI检测器

        Args:
            frame_width: 视频帧宽度
            frame_height: 视频帧高度
            roi_size: ROI区域的大小(正方形边长)
            content_change_threshold: 内容变化检测阈值
        """
        self.frame_width = frame_width
        self.frame_height = frame_height
        self.roi_size = roi_size
        self.content_change_threshold = content_change_threshold

        # 上一帧的灰度图像，用于内容变化检测
        self.prev_gray = None

        # 当前的ROI区域
        self.current_roi = {
            'x': 0,
            'y': 0,
            'width': roi_size,
            'height': roi_size
        }

    def detect_roi(self,
                   frame: np.ndarray,
                   mouse_pos: Tuple[int, int] = None) -> Dict[str, Any]:
        """
        在当前帧中检测ROI区域

        Args:
            frame: 当前视频帧(numpy数组)
            mouse_pos: 当前鼠标位置(x, y)，如果为None则不考虑鼠标

        Returns:
            包含ROI信息的字典: {'x', 'y', 'width', 'height', 'importance'}
        """
        roi = self._get_mouse_based_roi(mouse_pos) if mouse_pos else self.current_roi

        # 如果有足够的帧历史，检测内容变化
        if frame.ndim == 3:  # 彩色图像
            current_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        else:  # 已经是灰度图像
            current_gray = frame

        if self.prev_gray is not None:
            # 计算帧差异来检测变化区域
            content_roi = self._detect_content_change(current_gray)

            # 将鼠标ROI与内容变化ROI合并
            if mouse_pos:
                roi = self._merge_rois(roi, content_roi)

        # 更新状态
        self.prev_gray = current_gray
        self.current_roi = roi

        # 为ROI添加重要性评分(1.0表示最重要)
        roi['importance'] = 1.0

        return roi

    def _get_mouse_based_roi(self, mouse_pos: Tuple[int, int]) -> Dict[str, Any]:
        """基于鼠标位置创建ROI区域"""
        mouse_x, mouse_y = mouse_pos

        # 确保ROI完全在帧内
        x = max(0, min(mouse_x - self.roi_size // 2, self.frame_width - self.roi_size))
        y = max(0, min(mouse_y - self.roi_size // 2, self.frame_height - self.roi_size))

        return {
            'x': x,
            'y': y,
            'width': self.roi_size,
            'height': self.roi_size
        }

    def _detect_content_change(self, current_gray: np.ndarray) -> Dict[str, Any]:
        """检测帧之间的内容变化区域"""
        # 计算帧差异
        frame_diff = cv2.absdiff(current_gray, self.prev_gray)

        # 应用阈值
        _, thresholded = cv2.threshold(
            frame_diff,
            int(255 * self.content_change_threshold),
            255,
            cv2.THRESH_BINARY
        )

        # 找到变化最大的区域
        contours, _ = cv2.findContours(
            thresholded,
            cv2.RETR_EXTERNAL,
            cv2.CHAIN_APPROX_SIMPLE
        )

        if contours:
            # 找到最大的轮廓
            largest_contour = max(contours, key=cv2.contourArea)
            x, y, w, h = cv2.boundingRect(largest_contour)

            # 确保ROI有最小尺寸
            if w < self.roi_size:
                x = max(0, x - (self.roi_size - w) // 2)
                w = self.roi_size
            if h < self.roi_size:
                y = max(0, y - (self.roi_size - h) // 2)
                h = self.roi_size

            # 确保在帧内
            x = min(x, self.frame_width - w)
            y = min(y, self.frame_height - h)

            return {'x': x, 'y': y, 'width': w, 'height': h}

        # 如果没有检测到变化，返回当前ROI
        return self.current_roi

    def _merge_rois(self,
                    mouse_roi: Dict[str, Any],
                    content_roi: Dict[str, Any]) -> Dict[str, Any]:
        """合并基于鼠标的ROI和基于内容变化的ROI"""
        # 简单策略：优先选择鼠标ROI，因为用户关注点更重要
        return mouse_roi

    def get_roi_mask(self, frame_shape: Tuple[int, int]) -> np.ndarray:
        """
        为编码器创建ROI掩码

        Args:
            frame_shape: 视频帧形状(高, 宽)

        Returns:
            形状为frame_shape的二值掩码，ROI区域为1，其他为0
        """
        mask = np.zeros(frame_shape, dtype=np.uint8)
        roi = self.current_roi
        mask[roi['y']:roi['y'] + roi['height'], roi['x']:roi['x'] + roi['width']] = 1
        return mask

    def draw_roi(self, frame: np.ndarray) -> np.ndarray:
        """
        在帧上绘制ROI区域(用于可视化)

        Args:
            frame: 要绘制的视频帧

        Returns:
            带有ROI矩形标记的帧
        """
        result = frame.copy()
        roi = self.current_roi
        cv2.rectangle(
            result,
            (roi['x'], roi['y']),
            (roi['x'] + roi['width'], roi['y'] + roi['height']),
            (0, 255, 0),  # 绿色
            2
        )
        return result