import av
import numpy as np
from typing import Dict, Any, Tuple, Optional, List
import io
import time
import queue
import threading
import logging

# 配置日志
logger = logging.getLogger(__name__)


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
                 frame_callback = None,
                 roi_qp_offset: int = -5):  # ROI区域QP偏移，负值表示更高质量
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
            frame_callback: 帧编码完成回调
            roi_qp_offset: ROI区域QP偏移值
        """
        # 参数验证
        if width <= 0 or height <= 0:
            raise ValueError("宽度和高度必须大于0")
        if fps <= 0 or fps > 120:
            raise ValueError("帧率必须在1-120之间")
        if bitrate <= 0:
            raise ValueError("码率必须大于0")
        if gop_size <= 0:
            raise ValueError("GOP大小必须大于0")
        if roi_qp_offset < -20 or roi_qp_offset > 20:
            raise ValueError("ROI QP偏移必须在-20到20之间")

        self.width = width
        self.height = height
        self.fps = fps
        self.codec = codec
        self.bitrate = bitrate
        self.gop_size = gop_size
        self.use_roi = use_roi
        self.frame_callback = frame_callback
        self.roi_qp_offset = roi_qp_offset

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

        logger.info(f"视频编码器初始化完成: {width}x{height}, {fps}fps, {bitrate/1000000:.1f}Mbps, ROI={use_roi}")

    def _setup_codec(self):
        """设置编码器和输出容器"""
        try:
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

            logger.info("编码器设置完成")
        except Exception as e:
            logger.error(f"设置编码器失败: {e}")
            raise

    def start(self):
        """启动编码器"""
        if self.running:
            logger.warning("编码器已经在运行")
            return

        try:
            self.running = True
            self.frame_count = 0
            self.last_fps_update = time.time()

            # 启动编码线程
            self.encode_thread = threading.Thread(target=self._encoding_loop)
            self.encode_thread.daemon = True
            self.encode_thread.start()

            logger.info(f"视频编码器已启动: {self.width}x{self.height}, {self.fps}fps, {self.bitrate / 1000000:.1f}Mbps")
        except Exception as e:
            logger.error(f"启动编码器失败: {e}")
            self.running = False
            raise

    def stop(self):
        """停止编码器"""
        if not self.running:
            logger.warning("编码器已经停止")
            return

        try:
            self.running = False

            if self.encode_thread:
                self.encode_thread.join(timeout=2.0)
                self.encode_thread = None

            # 关闭容器
            if hasattr(self, 'container') and self.container:
                self.container.close()

            logger.info("视频编码器已停止")
        except Exception as e:
            logger.error(f"停止编码器时出错: {e}")

    def _encoding_loop(self):
        """编码线程主循环"""
        logger.info("编码线程已启动")
        
        while self.running:
            try:
                # 从队列获取帧和ROI信息
                frame_data, roi_info = self.packet_queue.get(timeout=0.1)

                # 编码帧
                packets = self._encode_frame(frame_data, roi_info)

                # 处理编码后的数据包
                if packets:
                    total_bytes = sum(len(packet) for packet in packets)
                    logger.debug(f"编码帧 #{self.frame_count}: {total_bytes} 字节")

                    # 调用回调函数（如果设置了）
                    if self.frame_callback:
                        for packet in packets:
                            # 构建帧信息
                            frame_info = {
                                'frame_count': self.frame_count,
                                'timestamp': time.time(),
                                'is_keyframe': False,  # 这里可能需要从编码器获取实际信息
                                'type': 'video_data',
                                'width': self.width,
                                'height': self.height,
                                'frame_id': self.frame_count
                            }
                            try:
                                self.frame_callback(packet, frame_info)
                            except Exception as e:
                                logger.error(f"帧回调异常: {e}")

                self.packet_queue.task_done()

            except queue.Empty:
                # 队列为空，继续等待
                continue
            except Exception as e:
                logger.error(f"编码线程异常: {e}")
                import traceback
                logger.error(f"异常详情: {traceback.format_exc()}")
                continue  # 继续运行，而不是退出循环

        logger.info("编码线程已结束")

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

        # 验证输入帧
        if frame is None:
            logger.error("输入帧为空")
            return False

        if frame.shape[0] != self.height or frame.shape[1] != self.width:
            logger.error(f"帧尺寸不匹配: 期望{self.width}x{self.height}, 实际{frame.shape[1]}x{frame.shape[0]}")
            return False

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
            logger.warning("编码队列已满，丢弃帧")
            return False

        # 添加到编码队列
        try:
            self.packet_queue.put((frame, roi_info))
            return True
        except Exception as e:
            logger.error(f"添加帧到队列失败: {e}")
            return False

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
        try:
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
            return [bytes(packet) for packet in packets]
        except Exception as e:
            logger.error(f"编码帧失败: {e}")
            return []

    def _apply_roi_encoding(self,
                            av_frame: av.VideoFrame,
                            roi_info: Dict[str, Any]):
        """
        应用ROI差异化编码

        Args:
            av_frame: PyAV视频帧
            roi_info: ROI信息
        """
        try:
            # 提取ROI信息
            roi_x = roi_info.get('x', 0)
            roi_y = roi_info.get('y', 0)
            roi_width = roi_info.get('width', 100)
            roi_height = roi_info.get('height', 100)
            importance = roi_info.get('importance', 1.0)

            # 计算ROI区域的QP偏移
            qp_offset = int(self.roi_qp_offset * importance)
            
            # 设置ROI区域的编码参数
            # 注意：PyAV的x264编码器支持通过x264-params设置ROI
            roi_params = f"roi={roi_x},{roi_y},{roi_width},{roi_height},{qp_offset}"
            
            # 更新编码器参数
            current_params = self.stream.options.get('x264-params', '')
            if current_params:
                new_params = f"{current_params}:{roi_params}"
            else:
                new_params = roi_params
            
            self.stream.options['x264-params'] = new_params
            
            logger.debug(f"应用ROI编码: 区域({roi_x},{roi_y},{roi_width},{roi_height}), QP偏移{qp_offset}")
            
        except Exception as e:
            logger.error(f"应用ROI编码失败: {e}")

    def get_encoding_fps(self) -> float:
        """获取当前实际编码帧率"""
        return self.encoding_fps

    def adjust_bitrate(self, new_bitrate: int):
        """
        调整编码码率

        Args:
            new_bitrate: 新的码率(bps)
        """
        if new_bitrate <= 0:
            logger.error("码率必须大于0")
            return

        # 只有在有明显变化时才重新设置编码器
        if abs(self.bitrate - new_bitrate) / self.bitrate > 0.1:  # 10%变化
            try:
                self.bitrate = new_bitrate
                self.stream.bit_rate = new_bitrate
                logger.info(f"已调整码率: {new_bitrate / 1000000:.1f}Mbps")
            except Exception as e:
                logger.error(f"调整码率失败: {e}")

    def adjust_gop_size(self, new_gop_size: int):
        """
        调整GOP大小

        Args:
            new_gop_size: 新的GOP大小
        """
        if new_gop_size <= 0:
            logger.error("GOP大小必须大于0")
            return

        if self.gop_size != new_gop_size:
            try:
                self.gop_size = new_gop_size
                # 更新编码器参数
                current_params = self.stream.options.get('x264-params', '')
                # 移除旧的keyint设置
                params_list = [p for p in current_params.split(':') if not p.startswith('keyint')]
                # 添加新的keyint设置
                params_list.append(f'keyint={new_gop_size}:min-keyint={new_gop_size}')
                self.stream.options['x264-params'] = ':'.join(params_list)
                
                logger.info(f"已调整GOP大小: {new_gop_size}")
            except Exception as e:
                logger.error(f"调整GOP大小失败: {e}")

    def force_keyframe(self):
        """强制生成关键帧"""
        try:
            # 在PyAV中，可以通过设置帧的key_frame属性来强制关键帧
            # 这里需要在编码时设置
            logger.info("强制生成关键帧")
        except Exception as e:
            logger.error(f"强制生成关键帧失败: {e}")

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
            'roi_qp_offset': self.roi_qp_offset,
            'encoding_fps': self.encoding_fps
        }

    def __del__(self):
        """清理资源"""
        try:
            self.stop()
        except:
            pass