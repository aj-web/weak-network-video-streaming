import av
import numpy as np
from typing import Dict, Any, Tuple, Optional, List
import io
import time
import queue
import threading


class VideoEncoder:
    """
    视频编码模块，负责将捕获的屏幕内容编码为视频流
    支持基于ROI的差异化编码
    """

    def __init__(self,
                 width: int,
                 height: int,
                 fps: int = 30,
                 codec: str = 'h264',
                 bitrate: int = 3000000,  # 3 Mbps
                 gop_size: int = 30,
                 use_roi: bool = True,
                 frame_callback = None):
        """
        初始化视频编码器

        Args:
            width: 视频宽度
            height: 视频高度
            fps: 帧率
            codec: 编码器，默认h264
            bitrate: 码率(bps)
            gop_size: 关键帧间隔
            use_roi: 是否使用ROI编码
        """
        self.width = width
        self.height = height
        self.fps = fps
        self.codec = codec
        self.bitrate = bitrate
        self.gop_size = gop_size
        self.use_roi = use_roi
        self.frame_callback = frame_callback

        # 编码器状态
        self.running = False
        self.frame_count = 0
        self.encoding_fps = 0
        self.last_fps_update = time.time()

        # 创建输出容器和编码器
        self._setup_codec()

        # 编码数据队列
        self.packet_queue = queue.Queue(maxsize=100)

        # 编码线程
        self.encode_thread = None

    def _setup_codec(self):
        """设置编码器和输出容器"""
        # 创建内存缓冲区作为输出
        self.output_buffer = io.BytesIO()

        # 创建容器
        self.container = av.open(self.output_buffer, mode='w', format='h264')

        # 创建视频流
        self.stream = self.container.add_stream(self.codec, rate=self.fps)
        self.stream.width = self.width
        self.stream.height = self.height
        self.stream.pix_fmt = 'yuv420p'

        # 设置编码器选项
        self.stream.options = {
            'crf': '23',  # 恒定速率因子(质量)
            'preset': 'ultrafast',  # 编码速度预设
            'tune': 'zerolatency',  # 低延迟调优
            'profile:v': 'baseline',  # 基准配置文件
            'level': '3.0',  # H.264级别
            'x264-params': f'keyint={self.gop_size}:min-keyint={self.gop_size}'  # GOP设置
        }

        # 如果指定了码率，则设置
        if self.bitrate > 0:
            self.stream.bit_rate = self.bitrate

    def start(self):
        """启动编码器"""
        if self.running:
            return

        self.running = True
        self.frame_count = 0
        self.last_fps_update = time.time()

        # 启动编码线程
        self.encode_thread = threading.Thread(target=self._encoding_loop)
        self.encode_thread.daemon = True
        self.encode_thread.start()

        print(f"视频编码器已启动: {self.width}x{self.height}, {self.fps}fps, {self.bitrate / 1000000:.1f}Mbps")

    def stop(self):
        """停止编码器"""
        self.running = False

        if self.encode_thread:
            self.encode_thread.join(timeout=1.0)
            self.encode_thread = None

        # 关闭容器
        if hasattr(self, 'container') and self.container:
            self.container.close()

        print("视频编码器已停止")

    def _encoding_loop(self):
        """编码线程主循环"""
        while self.running:
            try:
                # 从队列获取帧和ROI信息
                frame_data, roi_info = self.packet_queue.get(timeout=0.1)

                # 编码帧
                packets = self._encode_frame(frame_data, roi_info)

                # 处理编码后的数据包
                if packets and self.frame_callback:
                    for packet in packets:
                        # 调用回调，传递编码后的数据和帧信息
                        self.frame_callback(packet, {
                            'frame_count': self.frame_count,
                            'is_keyframe': False,  # 这里需要从编码器获取实际的关键帧信息
                            'timestamp': time.time()
                        })

                self.packet_queue.task_done()

            except queue.Empty:
                # 队列为空，继续等待
                continue
            except Exception as e:
                print(f"编码线程异常: {e}")
                import traceback
                traceback.print_exc()  # 打印详细的异常信息
                continue  # 继续运行，而不是退出循环

    def encode_frame(self,
                     frame: np.ndarray,
                     roi_info: Optional[Dict[str, Any]] = None) -> bool:
        """
        将视频帧加入编码队列

        Args:
            frame: 要编码的视频帧(numpy数组)
            roi_info: ROI信息

        Returns:
            是否成功加入队列
        """
        if not self.running:
            self.start()

        # 更新状态
        self.frame_count += 1
        current_time = time.time()
        elapsed = current_time - self.last_fps_update

        if elapsed >= 1.0:
            self.encoding_fps = self.frame_count / elapsed
            self.frame_count = 0
            self.last_fps_update = current_time

        # 检查队列是否已满
        if self.packet_queue.full():
            print("警告: 编码队列已满，丢弃帧")
            return False

        # 添加到编码队列
        self.packet_queue.put((frame, roi_info))
        return True

    def _encode_frame(self,
                      frame: np.ndarray,
                      roi_info: Optional[Dict[str, Any]]) -> List[bytes]:
        """
        编码单个视频帧

        Args:
            frame: 要编码的视频帧
            roi_info: ROI信息

        Returns:
            编码后的数据包列表
        """
        # 如果输入是BGRA格式，转换为RGB
        if frame.shape[2] == 4:
            frame = frame[:, :, :3]

        # 创建PyAV视频帧
        av_frame = av.VideoFrame.from_ndarray(frame, format='rgb24')

        # 如果启用了ROI并且有ROI信息，应用ROI编码
        if self.use_roi and roi_info:
            self._apply_roi_encoding(av_frame, roi_info)

        # 编码帧
        packets = self.stream.encode(av_frame)

        # 将数据包转换为字节列表
        # 修复: PyAV的Packet对象没有to_bytes方法，使用其buffer属性获取二进制数据
        return [bytes(packet) for packet in packets]

    def _apply_roi_encoding(self,
                            av_frame: av.VideoFrame,
                            roi_info: Dict[str, Any]):
        """
        应用ROI差异化编码

        Args:
            av_frame: PyAV视频帧
            roi_info: ROI信息
        """
        # 在实际实现中，这将设置x264编码器的区域感知参数
        # 但这需要低级的x264编码器访问，这里只是个占位符
        # 可以通过调整量化参数(QP)地图来实现

        # 在实际应用中，这可能需要使用FFmpeg的C API
        # 或编写自定义的Python扩展
        pass

    def get_encoding_fps(self) -> float:
        """获取当前实际编码帧率"""
        return self.encoding_fps

    def adjust_bitrate(self, new_bitrate: int):
        """
        调整编码码率

        Args:
            new_bitrate: 新的码率(bps)
        """
        # 只有在有明显变化时才重新设置编码器
        if abs(self.bitrate - new_bitrate) / self.bitrate > 0.1:  # 10%变化
            self.bitrate = new_bitrate
            self.stream.bit_rate = new_bitrate
            print(f"已调整码率: {new_bitrate / 1000000:.1f}Mbps")

    def adjust_gop_size(self, new_gop_size: int):
        """
        调整GOP大小

        Args:
            new_gop_size: 新的GOP大小
        """
        if self.gop_size != new_gop_size:
            self.gop_size = new_gop_size

            # 在PyAV中，这需要重新创建编码器
            # 这里简化处理，只记录更改
            print(f"已调整GOP大小: {new_gop_size}")

    def force_keyframe(self):
        """强制生成关键帧"""
        # 在PyAV中实现这个需要特殊处理
        # 这里只是一个占位符
        print("强制生成关键帧")

    def get_current_settings(self) -> Dict[str, Any]:
        """获取当前编码器设置"""
        return {
            'width': self.width,
            'height': self.height,
            'fps': self.fps,
            'codec': self.codec,
            'bitrate': self.bitrate,
            'gop_size': self.gop_size,
            'use_roi': self.use_roi,
            'encoding_fps': self.encoding_fps
        }

    def __del__(self):
        """清理资源"""
        self.stop()