# server/encoder/roi_detector.py

import cv2
import numpy as np
import time
from threading import Thread
import pyautogui

class ROIDetector:
    """区域重要性检测器"""
    
    def __init__(self, width, height, grid_size=8):
        """
        初始化ROI检测器
        
        Args:
            width: 视频宽度
            height: 视频高度
            grid_size: 网格大小(将画面划分为grid_size×grid_size个网格)
        """
        self.width = width
        self.height = height
        self.grid_size = grid_size
        
        # 计算网格尺寸
        self.grid_width = width // grid_size
        self.grid_height = height // grid_size
        
        # 最近一次检测的帧
        self.last_frame = None
        
        # 鼠标位置
        self.mouse_position = (0, 0)
        self.mouse_radius = 200  # 鼠标ROI半径(像素)
        
        # 运动检测参数
        self.motion_threshold = 20  # 像素差异阈值
        self.prev_gray = None  # 上一帧的灰度图
        
        # ROI权重矩阵(grid_size×grid_size)
        self.roi_weights = np.zeros((grid_size, grid_size), dtype=np.float32)
        
        # 启动鼠标跟踪线程
        self.is_running = True
        self.mouse_thread = Thread(target=self._track_mouse)
        self.mouse_thread.daemon = True
        self.mouse_thread.start()
    
    def _track_mouse(self):
        """鼠标位置跟踪线程"""
        while self.is_running:
            try:
                # 获取当前鼠标位置
                x, y = pyautogui.position()
                
                # 转换为视频坐标系
                x = int(x * (self.width / pyautogui.size()[0]))
                y = int(y * (self.height / pyautogui.size()[1]))
                
                self.mouse_position = (x, y)
                
                # 更新频率不需要太高
                time.sleep(0.05)
            except:
                pass
    
    def detect(self, frame):
        """
        检测ROI区域
        
        Args:
            frame: 输入帧(numpy数组)
            
        Returns:
            ROI权重矩阵(grid_size×grid_size)
        """
        # 保存当前帧
        self.last_frame = frame
        
        # 重置ROI权重
        self.roi_weights.fill(0.0)
        
        # 1. 鼠标位置ROI
        self._detect_mouse_roi()
        
        # 2. 运动检测ROI
        self._detect_motion_roi(frame)
        
        # 3. 文本检测ROI(简化版)
        self._detect_text_roi(frame)
        
        # 归一化ROI权重
        max_weight = np.max(self.roi_weights)
        if max_weight > 0:
            self.roi_weights = self.roi_weights / max_weight
        
        return self.roi_weights
    
    def _detect_mouse_roi(self):
        """基于鼠标位置的ROI检测"""
        x, y = self.mouse_position
        
        # 转换为网格坐标
        grid_x = min(x // self.grid_width, self.grid_size - 1)
        grid_y = min(y // self.grid_height, self.grid_size - 1)
        
        # 以鼠标位置为中心，设置ROI权重
        for i in range(max(0, grid_x-1), min(self.grid_size, grid_x+2)):
            for j in range(max(0, grid_y-1), min(self.grid_size, grid_y+2)):
                # 计算网格中心到鼠标的距离
                center_x = (i + 0.5) * self.grid_width
                center_y = (j + 0.5) * self.grid_height
                distance = np.sqrt((center_x - x)**2 + (center_y - y)**2)
                
                # 根据距离设置权重
                if distance < self.mouse_radius:
                    weight = 1.0 - (distance / self.mouse_radius)
                    self.roi_weights[j, i] = max(self.roi_weights[j, i], weight)
    
    def _detect_motion_roi(self, frame):
        """基于运动检测的ROI"""
        # 转换为灰度图
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        if self.prev_gray is not None:
            # 计算帧差
            frame_diff = cv2.absdiff(gray, self.prev_gray)
            
            # 阈值处理
            _, thresh = cv2.threshold(frame_diff, self.motion_threshold, 255, cv2.THRESH_BINARY)
            
            # 对每个网格计算运动量
            for i in range(self.grid_size):
                for j in range(self.grid_size):
                    # 计算网格区域
                    x1 = i * self.grid_width
                    y1 = j * self.grid_height
                    x2 = min(x1 + self.grid_width, self.width)
                    y2 = min(y1 + self.grid_height, self.height)
                    
                    # 提取网格区域
                    grid_thresh = thresh[y1:y2, x1:x2]
                    
                    # 计算运动像素比例
                    if grid_thresh.size > 0:
                        motion_ratio = np.count_nonzero(grid_thresh) / grid_thresh.size
                        
                        # 更新ROI权重
                        self.roi_weights[j, i] = max(self.roi_weights[j, i], motion_ratio)
        
        # 更新上一帧
        self.prev_gray = gray
    
    def _detect_text_roi(self, frame):
        """基于文本检测的ROI(简化版)"""
        # 转换为灰度图
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # 对每个网格检测文本可能性
        for i in range(self.grid_size):
            for j in range(self.grid_size):
                # 计算网格区域
                x1 = i * self.grid_width
                y1 = j * self.grid_height
                x2 = min(x1 + self.grid_width, self.width)
                y2 = min(y1 + self.grid_height, self.height)
                
                # 提取网格区域
                grid_gray = gray[y1:y2, x1:x2]
                
                if grid_gray.size > 0:
                    # 简单的边缘检测来估计文本
                    edges = cv2.Canny(grid_gray, 50, 150)
                    edge_ratio = np.count_nonzero(edges) / grid_gray.size
                    
                    # 文本通常有较多边缘
                    if edge_ratio > 0.1:
                        self.roi_weights[j, i] = max(self.roi_weights[j, i], edge_ratio * 0.5)
    
    def get_qp_delta_map(self, base_qp, max_delta=10):
        """
        获取QP调整映射
        
        Args:
            base_qp: 基础QP值
            max_delta: 最大QP调整值
            
        Returns:
            QP调整映射(grid_size×grid_size)
        """
        # 根据ROI权重计算QP调整值
        qp_delta_map = np.zeros_like(self.roi_weights)
        
        for i in range(self.grid_size):
            for j in range(self.grid_size):
                # ROI权重越高，QP调整越小(负值)
                qp_delta_map[j, i] = int((1.0 - self.roi_weights[j, i]) * max_delta)
        
        return qp_delta_map
    
    def get_roi_visualization(self):
        """
        获取ROI可视化图像
        
        Returns:
            可视化图像
        """
        if self.last_frame is None:
            return None
        
        # 创建可视化图像
        vis_image = self.last_frame.copy()
        
        # 绘制网格
        for i in range(1, self.grid_size):
            x = i * self.grid_width
            cv2.line(vis_image, (x, 0), (x, self.height), (255, 255, 255), 1)
        
        for j in range(1, self.grid_size):
            y = j * self.grid_height
            cv2.line(vis_image, (0, y), (self.width, y), (255, 255, 255), 1)
        
        # 根据ROI权重添加半透明叠加
        overlay = np.zeros_like(vis_image)
        
        for i in range(self.grid_size):
            for j in range(self.grid_size):
                # 计算网格区域
                x1 = i * self.grid_width
                y1 = j * self.grid_height
                x2 = min(x1 + self.grid_width, self.width)
                y2 = min(y1 + self.grid_height, self.height)
                
                # 根据ROI权重设置颜色
                weight = self.roi_weights[j, i]
                color = (0, int(255 * weight), 0)  # 绿色，权重越高颜色越深
                
                # 填充网格
                cv2.rectangle(overlay, (x1, y1), (x2, y2), color, -1)
        
        # 添加半透明叠加
        cv2.addWeighted(vis_image, 0.7, overlay, 0.3, 0, vis_image)
        
        # 绘制鼠标位置
        x, y = self.mouse_position
        cv2.circle(vis_image, (x, y), 10, (0, 0, 255), -1)
        cv2.circle(vis_image, (x, y), self.mouse_radius, (0, 0, 255), 2)
        
        return vis_image
    
    def cleanup(self):
        """清理资源"""
        self.is_running = False
        if self.mouse_thread:
            self.mouse_thread.join(timeout=1.0)