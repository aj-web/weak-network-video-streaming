# server/encoder/adaptive_encoder.py

import time
import threading
import numpy as np
import cv2
from queue import Queue

# server/encoder/adaptive_encoder.py (续)

class AdaptiveEncoder:
    """自适应视频编码器"""
    
    def __init__(self, width, height, fps, initial_bitrate, 
                 codec='h264', preset='ultrafast', gop=30):
        """
        初始化自适应编码器
        
        Args:
            width: 视频宽度
            height: 视频高度
            fps: 帧率
            initial_bitrate: 初始比特率(bps)
            codec: 编码器('h264', 'h265')
            preset: 编码预设('ultrafast', 'superfast', 'veryfast', ...)
            gop: GOP大小(I帧间隔)
        """
        self.width = width
        self.height = height
        self.fps = fps
        self.target_bitrate = initial_bitrate
        self.codec = codec
        self.preset = preset
        self.gop = gop
        
        # 当前编码参数
        self.current_params = {
            "width": width,
            "height": height,
            "fps": fps,
            "bitrate": initial_bitrate,
            "codec": codec,
            "preset": preset,
            "gop": gop,
            "base_qp": 23  # 基础量化参数
        }
        
        # 是否使用ROI编码
        self.use_roi = True
        self.roi_detector = None
        
        # 编码器实例
        self._init_encoder()
        
        # 输入输出队列
        self.input_queue = Queue(maxsize=60)
        self.output_queue = Queue(maxsize=60)
        
        # 控制标志
        self.is_running = False
        self.encode_thread = None
        
        # 性能统计
        self.stats = {
            "encoded_frames": 0,
            "dropped_frames": 0,
            "avg_encode_time": 0,
            "current_bitrate": 0
        }
        
        # 网络反馈
        self.network_feedback = {
            "rtt": 100,           # ms
            "packet_loss": 0.01,  # 1%
            "bandwidth": 5000000,  # bps
            "congestion": 0.0     # 0-1
        }
    
    def _init_encoder(self):
        """初始化编码器"""
        # 根据编码器类型选择不同的实现
        if self.codec == 'h264':
            # 使用x264编码器
            self._init_x264_encoder()
        elif self.codec == 'h265':
            # 使用x265编码器
            self._init_x265_encoder()
        else:
            raise ValueError(f"Unsupported codec: {self.codec}")
    
    def _init_x264_encoder(self):
        """初始化x264编码器"""
        # 配置x264参数
        gst_pipeline = (
            f'appsrc ! videoconvert ! '
            f'x264enc bitrate={self.target_bitrate//1000} speed-preset={self.preset} '
            f'tune=zerolatency key-int-max={self.gop} ! '
            f'video/x-h264, profile=baseline ! '
            f'appsink'
        )
        
        self.encoder = cv2.VideoWriter(
            gst_pipeline, cv2.CAP_GSTREAMER, 0, self.fps, (self.width, self.height), True
        )
        
        if not self.encoder.isOpened():
            # 如果GStreamer不可用，尝试使用OpenCV的内置编码器
            print("Warning: GStreamer pipeline failed, falling back to OpenCV encoder")
            fourcc = cv2.VideoWriter_fourcc(*'H264')
            self.encoder = cv2.VideoWriter(
                'output_temp.mp4', fourcc, self.fps, (self.width, self.height), True
            )
            
            if not self.encoder.isOpened():
                raise RuntimeError("Failed to initialize video encoder")
    
    def _init_x265_encoder(self):
        """初始化x265编码器"""
        # 配置x265参数
        gst_pipeline = (
            f'appsrc ! videoconvert ! '
            f'x265enc bitrate={self.target_bitrate//1000} speed-preset={self.preset} '
            f'tune=zerolatency key-int-max={self.gop} ! '
            f'video/x-h265 ! '
            f'appsink'
        )
        
        self.encoder = cv2.VideoWriter(
            gst_pipeline, cv2.CAP_GSTREAMER, 0, self.fps, (self.width, self.height), True
        )
        
        if not self.encoder.isOpened():
            # 如果GStreamer不可用，尝试使用OpenCV的内置编码器
            print("Warning: GStreamer pipeline failed, falling back to OpenCV encoder")
            fourcc = cv2.VideoWriter_fourcc(*'HEVC')
            self.encoder = cv2.VideoWriter(
                'output_temp.mp4', fourcc, self.fps, (self.width, self.height), True
            )
            
            if not self.encoder.isOpened():
                raise RuntimeError("Failed to initialize video encoder")
    
    def set_roi_detector(self, roi_detector):
        """
        设置ROI检测器
        
        Args:
            roi_detector: ROI检测器实例
        """
        self.roi_detector = roi_detector
    
    def start(self):
        """开始编码线程"""
        if self.is_running:
            return
            
        self.is_running = True
        self.encode_thread = threading.Thread(target=self._encode_loop)
        self.encode_thread.daemon = True
        self.encode_thread.start()
        print(f"Adaptive encoder started: {self.width}x{self.height}, {self.fps} FPS, {self.target_bitrate/1000000:.2f} Mbps")
    
    def stop(self):
        """停止编码线程"""
        self.is_running = False
        if self.encode_thread:
            self.encode_thread.join(timeout=1.0)
            self.encode_thread = None
        
        if self.encoder:
            self.encoder.release()
        print("Adaptive encoder stopped")
    
    def encode_frame(self, frame, block=False, timeout=None):
        """
        将帧放入编码队列
        
        Args:
            frame: 要编码的帧(numpy数组)
            block: 是否阻塞等待
            timeout: 超时时间(秒)
            
        Returns:
            是否成功放入队列
        """
        try:
            self.input_queue.put(frame, block=block, timeout=timeout)
            return True
        except:
            self.stats["dropped_frames"] += 1
            return False
    
    def get_packet(self, block=True, timeout=None):
        """
        获取编码后的数据包
        
        Args:
            block: 是否阻塞等待
            timeout: 超时时间(秒)
            
        Returns:
            编码后的数据包，或超时/队列为空时返回None
        """
        try:
            return self.output_queue.get(block=block, timeout=timeout)
        except:
            return None
    
    def update_network_feedback(self, feedback):
        """
        更新网络反馈
        
        Args:
            feedback: 网络反馈信息，包含rtt, packet_loss, bandwidth等
        """
        self.network_feedback.update(feedback)
        
        # 根据网络反馈调整编码参数
        self._adapt_to_network()
    
    def _adapt_to_network(self):
        """根据网络反馈调整编码参数"""
        # 计算可用带宽(考虑丢包率和RTT)
        available_bw = self.network_feedback["bandwidth"] * (1.0 - self.network_feedback["packet_loss"])
        
        # 调整目标码率(保留20%余量)
        target_bitrate = int(available_bw * 0.8)
        
        # 限制码率变化幅度(不超过当前的50%)
        max_increase = self.current_params["bitrate"] * 1.5
        min_decrease = self.current_params["bitrate"] * 0.5
        
        target_bitrate = min(max_increase, max(min_decrease, target_bitrate))
        
        # 根据不同网络条件调整参数
        if self.network_feedback["rtt"] < 100 and self.network_feedback["packet_loss"] < 0.02:
            # 良好网络: 高质量
            new_params = {
                "width": self.width,
                "height": self.height,
                "fps": self.fps,
                "bitrate": target_bitrate,
                "base_qp": 23
            }
        elif self.network_feedback["rtt"] < 200 and self.network_feedback["packet_loss"] < 0.05:
            # 中等网络: 平衡质量
            new_params = {
                "width": int(self.width * 0.75),
                "height": int(self.height * 0.75),
                "fps": min(self.fps, 30),
                "bitrate": target_bitrate,
                "base_qp": 26
            }
        elif self.network_feedback["rtt"] < 300 and self.network_feedback["packet_loss"] < 0.1:
            # 较差网络: 降低质量
            new_params = {
                "width": int(self.width * 0.5),
                "height": int(self.height * 0.5),
                "fps": min(self.fps, 20),
                "bitrate": target_bitrate,
                "base_qp": 29
            }
        else:
            # 非常差网络: 最低质量
            new_params = {
                "width": int(self.width * 0.35),
                "height": int(self.height * 0.35),
                "fps": min(self.fps, 10),
                "bitrate": target_bitrate,
                "base_qp": 32
            }
        
        # 检查是否需要重新初始化编码器
        need_reinit = (
            self.current_params["width"] != new_params["width"] or
            self.current_params["height"] != new_params["height"] or
            self.current_params["fps"] != new_params["fps"]
        )
        
        # 更新参数
        self.current_params.update(new_params)
        self.target_bitrate = new_params["bitrate"]
        
        # 如果需要，重新初始化编码器
        if need_reinit:
            self.width = new_params["width"]
            self.height = new_params["height"]
            self.fps = new_params["fps"]
            
            # 重新初始化编码器(需要在编码线程中进行)
            # 这里设置一个标志，由编码线程处理
            self.need_reinit = True
    
    def _encode_loop(self):
        """编码线程主循环"""
        cumulative_encode_time = 0
        encode_count = 0
        frame_index = 0
        
        while self.is_running:
            # 检查是否需要重新初始化编码器
            if hasattr(self, 'need_reinit') and self.need_reinit:
                if self.encoder:
                    self.encoder.release()
                self._init_encoder()
                self.need_reinit = False
            
            # 从输入队列获取帧
            try:
                frame = self.input_queue.get(block=True, timeout=0.1)
            except:
                continue
            
            # 调整帧大小(如果需要)
            if frame.shape[1] != self.current_params["width"] or frame.shape[0] != self.current_params["height"]:
                frame = cv2.resize(frame, (self.current_params["width"], self.current_params["height"]))
            
            # 检测ROI(如果启用)
            roi_map = None
            if self.use_roi and self.roi_detector:
                roi_map = self.roi_detector.detect(frame)
            
            # 编码帧
            start_time = time.time()
            
            # 处理ROI(如果有)
            if roi_map is not None:
                # 获取QP调整映射
                qp_delta_map = self.roi_detector.get_qp_delta_map(
                    self.current_params["base_qp"], max_delta=10
                )
                
                # TODO: 在真实实现中，我们会根据qp_delta_map调整每个宏块的QP
                # 但OpenCV不直接支持这种精细控制，所以这里只是模拟
                
                # 实际中可以使用x264_param_t和x264_picture_t结构体设置per-MB QP
                pass
            
            # 将帧写入编码器
            self.encoder.write(frame)
            
            # 在真实实现中，我们会从编码器获取压缩后的数据
            # 但OpenCV不直接提供这个功能，所以这里模拟一个输出
            
            # 估计编码大小(基于目标码率)
            frame_bits = self.target_bitrate / self.fps
            frame_bytes = int(frame_bits / 8)
            
            # 生成模拟的压缩数据
            is_keyframe = (frame_index % self.gop == 0)
            if is_keyframe:
                # 关键帧通常更大
                frame_bytes = int(frame_bytes * 3)
            
            # 创建模拟的编码数据
            # 注意: 实际实现应从编码器获取真实的压缩数据
            encoded_data = np.random.bytes(frame_bytes)
            
            encode_time = time.time() - start_time
            cumulative_encode_time += encode_time
            encode_count += 1
            
            # 更新统计信息
            self.stats["avg_encode_time"] = cumulative_encode_time / encode_count
            self.stats["encoded_frames"] += 1
            self.stats["current_bitrate"] = frame_bytes * 8 * self.fps  # bps
            
            # 将编码后的数据放入输出队列
            try:
                packet = {
                    "data": encoded_data,
                    "timestamp": time.time(),
                    "frame_index": frame_index,
                    "is_keyframe": is_keyframe,
                    "width": self.current_params["width"],
                    "height": self.current_params["height"],
                    "encoding_params": self.current_params.copy()
                }
                self.output_queue.put(packet, block=False)
            except:
                pass
            
            frame_index += 1