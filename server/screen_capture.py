import time
import numpy as np
from typing import Tuple, Optional
import mss
import mss.tools
import threading


class ScreenCapturer:
    """屏幕捕获模块，负责高效捕获屏幕内容和跟踪鼠标位置"""

    def __init__(self, monitor_number: int = 1, capture_rate: int = 30):
        """
        初始化屏幕捕获器

        Args:
            monitor_number: 要捕获的显示器编号(从1开始)
            capture_rate: 目标捕获帧率(fps)
        """
        # 在每个线程创建自己的MSS实例
        self.monitor_number = monitor_number

        # 初始化一次MSS来获取监视器信息
        with mss.mss() as sct:
            self.monitor = sct.monitors[monitor_number]  # 主显示器通常是1
            self.frame_width = self.monitor["width"]
            self.frame_height = self.monitor["height"]

        # 捕获参数
        self.capture_rate = capture_rate
        self.frame_time = 1.0 / capture_rate

        # 状态变量
        self.last_capture_time = 0
        self.frame_count = 0
        self.current_fps = 0
        self.running = False

        # 最近捕获的帧
        self.current_frame = None

        # 线程本地存储
        self.thread_local = threading.local()

        # 线程锁，用于同步对共享资源的访问
        self.lock = threading.Lock()

        print(f"初始化屏幕捕获，显示器尺寸: {self.frame_width}x{self.frame_height}")

    def _ensure_mss(self):
        """确保当前线程有MSS实例"""
        if not hasattr(self.thread_local, 'sct'):
            self.thread_local.sct = mss.mss()

    def start(self):
        """开始屏幕捕获过程"""
        self.running = True
        self.last_capture_time = time.time()
        self.frame_count = 0
        print("屏幕捕获已启动")

    def stop(self):
        """停止屏幕捕获过程"""
        self.running = False
        print("屏幕捕获已停止")

        # 清理资源
        if hasattr(self.thread_local, 'sct'):
            self.thread_local.sct.close()

    def get_monitor_size(self) -> Tuple[int, int]:
        """获取显示器尺寸"""
        return self.frame_width, self.frame_height

    def capture_frame(self) -> np.ndarray:
        """
        捕获当前屏幕帧

        Returns:
            numpy数组，形状为(高, 宽, 4)的BGRA格式图像
        """
        if not self.running:
            self.start()

        # 计算是否应该捕获新帧(基于目标帧率)
        current_time = time.time()
        elapsed = current_time - self.last_capture_time

        # 如果时间间隔小于目标帧时间，返回最近的帧
        with self.lock:
            if elapsed < self.frame_time and self.current_frame is not None:
                return self.current_frame

        # 确保有MSS实例
        self._ensure_mss()

        # 捕获新帧
        try:
            screenshot = self.thread_local.sct.grab(self.monitor)
            img = np.array(screenshot)

            # 更新状态
            with self.lock:
                self.current_frame = img
                self.frame_count += 1

                # 每秒更新一次FPS计算
                if current_time - self.last_capture_time >= 1.0:
                    self.current_fps = self.frame_count / (current_time - self.last_capture_time)
                    self.frame_count = 0
                    self.last_capture_time = current_time

            return img
        except Exception as e:
            print(f"捕获帧时出错: {e}")
            # 如果捕获失败，返回空帧或最近的帧
            with self.lock:
                if self.current_frame is not None:
                    return self.current_frame
                else:
                    # 创建黑色帧
                    return np.zeros((self.frame_height, self.frame_width, 4), dtype=np.uint8)

    def get_current_fps(self) -> float:
        """获取当前的实际捕获帧率"""
        return self.current_fps

    def get_mouse_position(self) -> Tuple[int, int]:
        """
        获取当前鼠标在显示器上的位置

        Returns:
            (x, y) 鼠标坐标
        """
        # 使用MSS库的get_position可能不可靠，使用其他库
        try:
            # 尝试使用pyautogui获取鼠标位置
            import pyautogui
            x, y = pyautogui.position()
            return x, y
        except ImportError:
            print("未安装pyautogui库，无法获取鼠标位置")
            return (0, 0)

    def __del__(self):
        """清理资源"""
        self.stop()