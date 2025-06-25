import numpy as np
from typing import Tuple, List, Dict, Any, Optional
import cv2
import logging

logger = logging.getLogger(__name__)

class ROIDetector:
    """
    感兴趣区域(ROI)检测器，用于识别视频帧中的重要区域
    基于鼠标位置和画面内容变化
    """

    def __init__(self,
                 frame_width: int,
                 frame_height: int,
                 roi_size: int = 200,
                 content_change_threshold: float = 0.05,
                 fusion_mode: str = 'mouse_first'):
        """
        初始化ROI检测器

        Args:
            frame_width: 视频帧宽度
            frame_height: 视频帧高度
            roi_size: ROI区域的大小(正方形边长)
            content_change_threshold: 内容变化检测阈值
            fusion_mode: ROI融合策略（'mouse_first'或'content_first'）
        """
        # 参数验证
        if frame_width <= 0 or frame_height <= 0:
            raise ValueError("帧宽高必须大于0")
        if roi_size <= 0 or roi_size > min(frame_width, frame_height):
            raise ValueError("ROI大小必须大于0且不超过帧尺寸")
        if not (0.0 < content_change_threshold < 1.0):
            raise ValueError("内容变化阈值必须在0~1之间")
        if fusion_mode not in ('mouse_first', 'content_first'):
            raise ValueError("fusion_mode必须为'mouse_first'或'content_first'")

        self.frame_width = frame_width
        self.frame_height = frame_height
        self.roi_size = roi_size
        self.content_change_threshold = content_change_threshold
        self.fusion_mode = fusion_mode

        # 上一帧的灰度图像，用于内容变化检测
        self.prev_gray = None

        # 当前的ROI区域
        self.current_roi = {
            'x': 0,
            'y': 0,
            'width': roi_size,
            'height': roi_size
        }

        logger.info(f"ROI检测器初始化: {frame_width}x{frame_height}, ROI大小={roi_size}, 阈值={content_change_threshold}, 策略={fusion_mode}")

    def detect_roi(self,
                   frame: np.ndarray,
                   mouse_pos: Optional[Tuple[int, int]] = None) -> Dict[str, Any]:
        """
        在当前帧中检测ROI区域

        Args:
            frame: 当前视频帧(numpy数组)
            mouse_pos: 当前鼠标位置(x, y)，如果为None则不考虑鼠标

        Returns:
            包含ROI信息的字典: {'x', 'y', 'width', 'height', 'importance'}
        """
        try:
            if frame is None or frame.shape[0] != self.frame_height or frame.shape[1] != self.frame_width:
                logger.error("输入帧尺寸不匹配或为空")
                return self.current_roi.copy()

            # 鼠标ROI
            mouse_roi = self._get_mouse_based_roi(mouse_pos) if mouse_pos else self.current_roi

            # 内容变化ROI
            if frame.ndim == 3:
                current_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            else:
                current_gray = frame

            content_roi = None
            if self.prev_gray is not None:
                content_roi = self._detect_content_change(current_gray)

            # 融合策略
            roi = mouse_roi
            if content_roi:
                if self.fusion_mode == 'mouse_first' and mouse_pos:
                    roi = self._merge_rois(mouse_roi, content_roi)
                elif self.fusion_mode == 'content_first':
                    roi = self._merge_rois(content_roi, mouse_roi)
                else:
                    roi = mouse_roi

            # 边界裁剪
            roi = self._clip_roi(roi)

            # 更新状态
            self.prev_gray = current_gray
            self.current_roi = roi

            # 为ROI添加重要性评分(1.0表示最重要)
            roi['importance'] = 1.0

            return roi.copy()
        except Exception as e:
            logger.error(f"ROI检测异常: {e}")
            return self.current_roi.copy()

    def _get_mouse_based_roi(self, mouse_pos: Tuple[int, int]) -> Dict[str, Any]:
        """基于鼠标位置创建ROI区域"""
        try:
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
        except Exception as e:
            logger.error(f"鼠标ROI计算异常: {e}")
            return self.current_roi.copy()

    def _detect_content_change(self, current_gray: np.ndarray) -> Optional[Dict[str, Any]]:
        """检测帧之间的内容变化区域"""
        try:
            frame_diff = cv2.absdiff(current_gray, self.prev_gray)
            _, thresholded = cv2.threshold(
                frame_diff,
                int(255 * self.content_change_threshold),
                255,
                cv2.THRESH_BINARY
            )
            contours, _ = cv2.findContours(
                thresholded,
                cv2.RETR_EXTERNAL,
                cv2.CHAIN_APPROX_SIMPLE
            )
            if contours:
                largest_contour = max(contours, key=cv2.contourArea)
                x, y, w, h = cv2.boundingRect(largest_contour)
                # 确保ROI有最小尺寸
                if w < self.roi_size:
                    x = max(0, x - (self.roi_size - w) // 2)
                    w = self.roi_size
                if h < self.roi_size:
                    y = max(0, y - (self.roi_size - h) // 2)
                    h = self.roi_size
                # 边界裁剪
                x = min(x, self.frame_width - w)
                y = min(y, self.frame_height - h)
                return {'x': x, 'y': y, 'width': w, 'height': h}
            return None
        except Exception as e:
            logger.error(f"内容变化ROI检测异常: {e}")
            return None

    def _merge_rois(self,
                    roi1: Dict[str, Any],
                    roi2: Dict[str, Any]) -> Dict[str, Any]:
        """合并两个ROI区域，取交集或并集（此处默认取鼠标优先）"""
        try:
            # 简单策略：优先选择第一个ROI
            return roi1.copy()
        except Exception as e:
            logger.error(f"ROI合并异常: {e}")
            return roi1.copy()

    def _clip_roi(self, roi: Dict[str, Any]) -> Dict[str, Any]:
        """裁剪ROI区域，确保在帧内"""
        try:
            x = max(0, min(roi['x'], self.frame_width - roi['width']))
            y = max(0, min(roi['y'], self.frame_height - roi['height']))
            w = min(roi['width'], self.frame_width)
            h = min(roi['height'], self.frame_height)
            return {'x': x, 'y': y, 'width': w, 'height': h}
        except Exception as e:
            logger.error(f"ROI裁剪异常: {e}")
            return self.current_roi.copy()

    def get_roi_mask(self, frame_shape: Tuple[int, int]) -> np.ndarray:
        """
        为编码器创建ROI掩码

        Args:
            frame_shape: 视频帧形状(高, 宽)

        Returns:
            形状为frame_shape的二值掩码，ROI区域为1，其他为0
        """
        try:
            mask = np.zeros(frame_shape, dtype=np.uint8)
            roi = self.current_roi
            y1, y2 = roi['y'], roi['y'] + roi['height']
            x1, x2 = roi['x'], roi['x'] + roi['width']
            mask[y1:y2, x1:x2] = 1
            return mask
        except Exception as e:
            logger.error(f"ROI掩码生成异常: {e}")
            return np.zeros(frame_shape, dtype=np.uint8)

    def draw_roi(self, frame: np.ndarray) -> np.ndarray:
        """
        在帧上绘制ROI区域(用于可视化)

        Args:
            frame: 要绘制的视频帧

        Returns:
            带有ROI矩形标记的帧
        """
        try:
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
        except Exception as e:
            logger.error(f"ROI可视化异常: {e}")
            return frame