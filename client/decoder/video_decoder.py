# client/decoder/video_decoder.py

import cv2
import numpy as np
import time
import threading
from queue import Queue

class VideoDecoder:
    """视频解码器"""
    
    def __init__(self):
        """初始化视频解码器"""
        # 帧队列
        self.input_queue = Queue(maxsize=30)
        self.output_queue = Queue(maxsize=30)
        
        # 控制标志
        self.is_running = False
        self.decode_thread = None
        
        # 最后一帧
        self.last_frame = None
        
        # 统计信息
        self.stats = {
            "decoded_frames": 0,
            "dropped_frames": 0,
            "avg_decode_time": 0
        }
    
    def start(self):
        """启动解码线程"""
        if self.is_running:
            return
            
        self.is_running = True
        self.decode_thread = threading.Thread(target=self._decode_loop)
        self.decode_thread.daemon = True
        self.decode_thread.start()
        print("Video decoder started")
    
    def stop(self):
        """停止解码线程"""
        self.is_running = False
        if self.decode_thread:
            self.decode_thread.join(timeout=1.0)
            self.decode_thread = None
        print("Video decoder stopped")
    
    def decode_frame(self, frame_data, block=False, timeout=None):
        """
        将帧数据放入解码队列
        
        Args:
            frame_data: 帧数据字典
            block: 是否阻塞等待
            timeout: 超时时间(秒)
            
        Returns:
            是否成功放入队列
        """
        try:
            self.input_queue.put(frame_data, block=block, timeout=timeout)
            return True
        except:
            self.stats["dropped_frames"] += 1
            return False
    
    def get_frame(self, block=True, timeout=None):
        """
        获取解码后的帧
        
        Args:
            block: 是否阻塞等待
            timeout: 超时时间(秒)
            
        Returns:
            解码后的帧(numpy数组)，或超时/队列为空时返回最后一帧或None
        """
        try:
            frame = self.output_queue.get(block=block, timeout=timeout)
            self.last_frame = frame
            return frame
        except:
            return self.last_frame
    
    def _decode_loop(self):
        """解码线程主循环"""
        cumulative_decode_time = 0
        decode_count = 0
        
        while self.is_running:
            # 从输入队列获取帧数据
            try:
                frame_data = self.input_queue.get(block=True, timeout=0.1)
            except:
                continue
            
            # 解码帧
            start_time = time.time()
            
            try:
                # 提取帧信息
                data = frame_data["data"]
                is_keyframe = frame_data["is_keyframe"]
                width = frame_data.get("width", 640)
                height = frame_data.get("height", 480)
                
                # 将字节数据转换为numpy数组
                nparr = np.frombuffer(data, np.uint8)
                
                # 解码图像
                decoded_frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                
                if decoded_frame is None:
                    print("Failed to decode frame")
                    continue
                
                # 调整图像大小（如果需要）
                if decoded_frame.shape[1] != width or decoded_frame.shape[0] != height:
                    decoded_frame = cv2.resize(decoded_frame, (width, height))
                
                decode_time = time.time() - start_time
                cumulative_decode_time += decode_time
                decode_count += 1
                
                # 更新统计信息
                self.stats["avg_decode_time"] = cumulative_decode_time / decode_count
                self.stats["decoded_frames"] += 1
                
                # 将解码后的帧放入输出队列
                try:
                    self.output_queue.put(decoded_frame, block=False)
                except:
                    self.stats["dropped_frames"] += 1
            except Exception as e:
                print(f"Error decoding frame: {e}")
                self.stats["dropped_frames"] += 1