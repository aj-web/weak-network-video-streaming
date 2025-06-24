# server/capture/screen_capturer.py

import cv2
import numpy as np
import time
import pyautogui
from threading import Thread
from queue import Queue

class ScreenCapturer:
    def __init__(self, width=None, height=None, fps=30):
        """
        初始化屏幕捕获器
        
        Args:
            width: 输出宽度，None表示使用原始分辨率
            height: 输出高度，None表示使用原始分辨率
            fps: 目标帧率
        """
        self.width = width
        self.height = height
        self.target_fps = fps
        self.frame_interval = 1.0 / fps
        
        # 获取屏幕分辨率
        screen_width, screen_height = pyautogui.size()
        self.screen_width = screen_width
        self.screen_height = screen_height
        
        # 如果未指定输出分辨率，使用屏幕分辨率
        if self.width is None:
            self.width = screen_width
        if self.height is None:
            self.height = screen_height
            
        # 帧队列
        self.frame_queue = Queue(maxsize=30)
        
        # 控制标志
        self.is_running = False
        self.capture_thread = None
        
        # 性能统计
        self.stats = {
            "captured_frames": 0,
            "dropped_frames": 0,
            "avg_capture_time": 0
        }
    
    def start(self):
        """开始捕获屏幕"""
        if self.is_running:
            return
            
        self.is_running = True
        self.capture_thread = Thread(target=self._capture_loop)
        self.capture_thread.daemon = True
        self.capture_thread.start()
        print(f"Screen capturer started at {self.width}x{self.height}, target {self.target_fps} FPS")
    
    def stop(self):
        """停止捕获屏幕"""
        self.is_running = False
        if self.capture_thread:
            self.capture_thread.join(timeout=1.0)
            self.capture_thread = None
        print("Screen capturer stopped")
    
    def get_frame(self, block=True, timeout=None):
        """
        获取一帧画面
        
        Args:
            block: 是否阻塞等待
            timeout: 超时时间(秒)
            
        Returns:
            numpy数组格式的图像帧，或超时/队列为空时返回None
        """
        try:
            return self.frame_queue.get(block=block, timeout=timeout)
        except:
            return None
    
    def _capture_loop(self):
        """屏幕捕获循环"""
        last_frame_time = time.time()
        cumulative_capture_time = 0
        capture_count = 0
        
        print(f"Screen capture loop started, target FPS: {self.target_fps}")
        
        while self.is_running:
            try:
                # 计算应该捕获下一帧的时间
                next_frame_time = last_frame_time + self.frame_interval
                current_time = time.time()
                
                # 如果时间还没到，等待
                if current_time < next_frame_time:
                    time.sleep(next_frame_time - current_time)
                
                # 捕获屏幕
                start_capture_time = time.time()
                screenshot = pyautogui.screenshot()
                
                # 转换为numpy数组并转换为BGR(OpenCV格式)
                frame = np.array(screenshot)
                frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
                
                # 调整大小(如果需要)
                if self.width != self.screen_width or self.height != self.screen_height:
                    frame = cv2.resize(frame, (self.width, self.height))
                
                capture_time = time.time() - start_capture_time
                cumulative_capture_time += capture_time
                capture_count += 1
                
                # 更新统计信息
                self.stats["avg_capture_time"] = cumulative_capture_time / capture_count
                self.stats["captured_frames"] += 1
                
                # 将帧放入队列，如果队列已满，则丢弃这一帧
                try:
                    self.frame_queue.put(frame, block=False)
                except:
                    self.stats["dropped_frames"] += 1
                
                # 更新上一帧时间
                last_frame_time = time.time()
                
                # 每100帧打印一次调试信息
                if capture_count % 100 == 1:
                    print(f"Screen capture: {capture_count} frames, avg time: {self.stats['avg_capture_time']*1000:.1f}ms, queue size: {self.frame_queue.qsize()}")
                    
            except Exception as e:
                print(f"Error in screen capture loop: {e}")
                time.sleep(0.1)  # 出错时短暂等待