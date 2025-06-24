# client/decoder/frame_reconstruction.py

import cv2
import numpy as np
import time

class FrameReconstructor:
    """帧重建器，用于恢复丢失或损坏的帧"""
    
    def __init__(self):
        """初始化帧重建器"""
        # 保存最近的几帧用于插值
        self.recent_frames = []
        self.max_frames = 5
        
        # 简单运动估计参数
        self.lk_params = dict(
            winSize=(15, 15),
            maxLevel=2,
            criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 10, 0.03)
        )
        
        # 特征点检测参数
        self.feature_params = dict(
            maxCorners=100,
            qualityLevel=0.3,
            minDistance=7,
            blockSize=7
        )
        
        # 统计信息
        self.stats = {
            "reconstructed_frames": 0,
            "avg_reconstruction_time": 0
        }
    
    def add_frame(self, frame):
        """
        添加一帧到历史记录
        
        Args:
            frame: 要添加的帧
        """
        self.recent_frames.append(frame.copy())
        
        # 限制历史记录大小
        if len(self.recent_frames) > self.max_frames:
            self.recent_frames.pop(0)
    
    def reconstruct_frame(self, prev_frame, next_frame, ratio=0.5):
        """
        重建中间帧
        
        Args:
            prev_frame: 前一帧
            next_frame: 后一帧
            ratio: 插值比例(0-1)，0表示与prev_frame相同，1表示与next_frame相同
            
        Returns:
            重建的帧
        """
        if prev_frame is None or next_frame is None:
            return None
        
        start_time = time.time()
        
        # 转换为灰度图像用于特征点检测
        prev_gray = cv2.cvtColor(prev_frame, cv2.COLOR_BGR2GRAY)
        next_gray = cv2.cvtColor(next_frame, cv2.COLOR_BGR2GRAY)
        
        # 检测特征点
        prev_points = cv2.goodFeaturesToTrack(prev_gray, **self.feature_params)
        
        if prev_points is None or len(prev_points) == 0:
            # 如果无法检测到特征点，使用简单的线性插值
            reconstructed = self._linear_interpolate(prev_frame, next_frame, ratio)
        else:
            # 使用光流跟踪特征点
            next_points, status, _ = cv2.calcOpticalFlowPyrLK(
                prev_gray, next_gray, prev_points, None, **self.lk_params
            )
            
            # 筛选有效的特征点
            good_prev = prev_points[status == 1]
            good_next = next_points[status == 1]
            
            if len(good_prev) < 4:
                # 如果有效特征点不足，使用简单的线性插值
                reconstructed = self._linear_interpolate(prev_frame, next_frame, ratio)
            else:
                # 使用特征点计算仿射变换
                reconstructed = self._motion_interpolate(prev_frame, next_frame, good_prev, good_next, ratio)
        
        reconstruction_time = time.time() - start_time
        
        # 更新统计信息
        self.stats["reconstructed_frames"] += 1
        avg_time = self.stats.get("avg_reconstruction_time", 0)
        count = self.stats["reconstructed_frames"]
        self.stats["avg_reconstruction_time"] = (avg_time * (count - 1) + reconstruction_time) / count
        
        return reconstructed
    
    def _linear_interpolate(self, prev_frame, next_frame, ratio):
        """简单的线性插值"""
        return cv2.addWeighted(prev_frame, 1.0 - ratio, next_frame, ratio, 0)
    
    def _motion_interpolate(self, prev_frame, next_frame, prev_points, next_points, ratio):
        """基于运动的插值"""
        # 计算中间点
        mid_points = prev_points * (1.0 - ratio) + next_points * ratio
        
        # 创建中间帧
        result = np.zeros_like(prev_frame)
        
        # 使用三角剖分和仿射变换
        # 这里我们使用一个简化版本
        height, width = prev_frame.shape[:2]
        
        # 计算整体的仿射变换
        transform = cv2.estimateAffinePartial2D(prev_points, mid_points)[0]
        
        # 应用仿射变换
        warped_prev = cv2.warpAffine(prev_frame, transform, (width, height))
        
        # 同样计算从next_frame到mid_points的变换
        transform_next = cv2.estimateAffinePartial2D(next_points, mid_points)[0]
        warped_next = cv2.warpAffine(next_frame, transform_next, (width, height))
        
        # 混合两个变换后的帧
        result = cv2.addWeighted(warped_prev, 1.0 - ratio, warped_next, ratio, 0)
        
        return result
    
    def repair_damaged_frame(self, damaged_frame, reference_frames=None):
        """
        修复损坏的帧
        
        Args:
            damaged_frame: 损坏的帧
            reference_frames: 参考帧列表，如果为None则使用历史帧
            
        Returns:
            修复后的帧
        """
        if reference_frames is None:
            reference_frames = self.recent_frames
        
        if not reference_frames:
            return damaged_frame
        
        # 简单修复：用最近的完好帧替换
        return reference_frames[-1].copy()