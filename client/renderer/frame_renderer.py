# client/renderer/frame_renderer.py

import cv2
import time
import threading
import numpy as np
from queue import Queue

class FrameRenderer:
    """视频帧渲染器"""
    
    def __init__(self, window_name="Video Stream"):
        """
        初始化帧渲染器
        
        Args:
            window_name: 窗口名称
        """
        self.window_name = window_name
        
        # 帧队列
        self.frame_queue = Queue(maxsize=5)
        
        # 控制标志
        self.is_running = False
        self.render_thread = None
        
        # 统计信息
        self.stats = {
            "rendered_frames": 0,
            "dropped_frames": 0,
            "avg_render_time": 0,
            "fps": 0
        }
        
        # FPS计算
        self.fps_count = 0
        self.fps_start_time = 0
        self.fps_update_interval = 1.0  # 秒
    
    def start(self):
        """启动渲染线程"""
        if self.is_running:
            return
            
        self.is_running = True
        self.render_thread = threading.Thread(target=self._render_loop)
        self.render_thread.daemon = True
        self.render_thread.start()
        
        # 创建窗口
        cv2.namedWindow(self.window_name, cv2.WINDOW_NORMAL)
        
        print("Frame renderer started")
    
    def stop(self):
        """停止渲染线程"""
        self.is_running = False
        
        if self.render_thread:
            self.render_thread.join(timeout=1.0)
            self.render_thread = None
        
        # 销毁窗口
        cv2.destroyAllWindows()
        
        print("Frame renderer stopped")
    
    def render_frame(self, frame, block=False, timeout=None):
        """
        将帧放入渲染队列
        
        Args:
            frame: 要渲染的帧(numpy数组)
            block: 是否阻塞等待
            timeout: 超时时间(秒)
            
        Returns:
            是否成功放入队列
        """
        try:
            self.frame_queue.put(frame, block=block, timeout=timeout)
            return True
        except:
            self.stats["dropped_frames"] += 1
            return False
    
    def _render_loop(self):
        """渲染线程主循环"""
        cumulative_render_time = 0
        render_count = 0
        
        # 初始化FPS计时器
        self.fps_count = 0
        self.fps_start_time = time.time()
        
        while self.is_running:
            # 从队列获取帧
            try:
                frame = self.frame_queue.get(block=True, timeout=0.1)
            except:
                continue
            
            # 渲染帧
            start_time = time.time()
            
            # 显示帧
            cv2.imshow(self.window_name, frame)
            
            # 检查键盘输入(ESC键退出)
            key = cv2.waitKey(1) & 0xFF
            if key == 27:  # ESC键
                self.is_running = False
                break
            
            render_time = time.time() - start_time
            cumulative_render_time += render_time
            render_count += 1
            
            # 更新FPS计数
            self.fps_count += 1
            current_time = time.time()
            time_diff = current_time - self.fps_start_time
            
            if time_diff >= self.fps_update_interval:
                self.stats["fps"] = self.fps_count / time_diff
                self.fps_count = 0
                self.fps_start_time = current_time
            
            # 更新统计信息
            self.stats["avg_render_time"] = cumulative_render_time / render_count
            self.stats["rendered_frames"] += 1