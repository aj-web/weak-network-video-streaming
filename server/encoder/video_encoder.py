# server/encoder/video_encoder.py

import cv2
import time
import numpy as np
from threading import Thread
from queue import Queue


class VideoEncoder:
    def __init__(self, width, height, fps, bitrate, codec='h264', preset='ultrafast', gop=30):
        """
        初始化视频编码器

        Args:
            width: 视频宽度
            height: 视频高度
            fps: 帧率
            bitrate: 比特率(bps)
            codec: 编码器('h264', 'h265')
            preset: 编码预设('ultrafast', 'superfast', 'veryfast', ...)
            gop: GOP大小(I帧间隔)
        """
        self.width = width
        self.height = height
        self.fps = fps
        self.bitrate = bitrate
        self.codec = codec
        self.preset = preset
        self.gop = gop

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

        print(f"Initialized JPEG encoder: {width}x{height}")

    def start(self):
        """开始编码线程"""
        if self.is_running:
            return

        self.is_running = True
        self.encode_thread = Thread(target=self._encode_loop)
        self.encode_thread.daemon = True
        self.encode_thread.start()
        print(f"Video encoder started: {self.width}x{self.height}, {self.fps} FPS, {self.bitrate / 1000000:.2f} Mbps")

    def stop(self):
        """停止编码线程"""
        self.is_running = False
        if self.encode_thread:
            self.encode_thread.join(timeout=1.0)
            self.encode_thread = None
        print("Video encoder stopped")

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

    def _encode_loop(self):
        """编码线程主循环"""
        cumulative_encode_time = 0
        encode_count = 0
        frame_index = 0

        while self.is_running:
            # 从输入队列获取帧
            try:
                frame = self.input_queue.get(block=True, timeout=0.1)
            except:
                continue

            # 编码帧
            start_time = time.time()

            try:
                # 确保帧大小正确
                if frame.shape[1] != self.width or frame.shape[0] != self.height:
                    frame = cv2.resize(frame, (self.width, self.height))

                # 使用JPEG编码
                is_keyframe = (frame_index % self.gop == 0)
                quality = 95 if is_keyframe else 90
                encode_params = [int(cv2.IMWRITE_JPEG_QUALITY), quality]

                # 编码为JPEG
                success, encoded_data = cv2.imencode('.jpg', frame, encode_params)

                if not success or encoded_data is None:
                    print("Failed to encode frame")
                    continue

                # 获取字节数据
                data_bytes = encoded_data.tobytes()
                data_size = len(data_bytes)

                if data_size == 0:
                    print("Warning: Encoded frame size is 0")
                    continue

                print(f"Encoded frame {frame_index}: {data_size} bytes, keyframe={is_keyframe}")

            encode_time = time.time() - start_time
            cumulative_encode_time += encode_time
            encode_count += 1

            # 更新统计信息
            self.stats["avg_encode_time"] = cumulative_encode_time / encode_count
            self.stats["encoded_frames"] += 1
            self.stats["current_bitrate"] = data_size * 8 * self.fps  # bps

        # 将编码后的数据放入输出队列
        try:
            packet = {
                "data": data_bytes,
                "timestamp": time.time(),
                "frame_index": frame_index,
                "is_keyframe": is_keyframe,
                "width": self.width,
                "height": self.height
            }
            self.output_queue.put(packet, block=False)
        except:
            self.stats["dropped_frames"] += 1

        frame_index += 1
