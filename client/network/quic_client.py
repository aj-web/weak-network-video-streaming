import asyncio
import logging
import ssl
import time
from typing import Dict, Any, Optional, List, Callable, Tuple
import json
import struct
import threading
import queue

from aioquic.asyncio import connect
from aioquic.asyncio.protocol import QuicConnectionProtocol
from aioquic.quic.configuration import QuicConfiguration
from aioquic.quic.events import QuicEvent, StreamDataReceived

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("quic_client")


class VideoStreamClient:
    """
    视频流客户端
    使用QUIC协议连接到服务端，接收视频流数据
    """

    def __init__(self,
                 host: str = "127.0.0.1",
                 port: int = 4433,
                 verify_ssl: bool = False):
        """
        初始化视频流客户端

        Args:
            host: 服务器地址
            port: 服务器端口
            verify_ssl: 是否验证SSL证书
        """
        self.host = host
        self.port = port
        self.verify_ssl = verify_ssl

        # 连接状态
        self.connected = False
        self.connection = None
        self.loop = None

        # 数据包序列号
        self.packet_id = 0

        # 连接统计信息
        self.stats = {
            'connected_at': 0,
            'bytes_received': 0,
            'packets_received': 0,
            'rtt': 0,
            'packet_loss': 0,
            'bandwidth': 0,
            'last_status_update': 0
        }

        # 回调函数
        self.video_frame_callback = None
        self.connection_status_callback = None

        # 网络状态
        self.last_rtt_samples = []
        self.last_bandwidth_samples = []

        # 接收数据队列
        self.video_queue = queue.Queue(maxsize=100)

        # 网络状态更新线程
        self.status_update_thread = None
        self.running = False

    async def connect(self):
        """连接到服务器(异步)"""
        if self.connected:
            logger.warning("已经连接到服务器")
            return

        logger.info(f"连接到服务器: {self.host}:{self.port}")

        try:
            # 创建QUIC配置
            configuration = QuicConfiguration(
                alpn_protocols=["video-streaming"],
                is_client=True,
                verify_mode=ssl.CERT_NONE if not self.verify_ssl else ssl.CERT_REQUIRED,
                idle_timeout=30.0,  # 增加空闲超时时间
                max_datagram_frame_size=65536
            )

            logger.info("开始连接...")

            # 创建客户端协议工厂
            def create_protocol(*args, **kwargs):
                logger.debug("创建客户端协议")
                protocol = QuicClientProtocol(*args, **kwargs)
                protocol.video_frame_callback = self._on_video_frame
                protocol._quic_logger = self._quic_logger
                return protocol

            # 连接到服务器
            async with connect(
                    self.host,
                    self.port,
                    configuration=configuration,
                    create_protocol=create_protocol,
                    session_ticket_handler=self._session_ticket_handler,
                    wait_connected=True
            ) as client:
                logger.info("连接已建立!")
                # 保存连接
                self.connection = client
                self.connected = True
                self.stats['connected_at'] = time.time()

                if self.connection_status_callback:
                    self.connection_status_callback({
                        'status': 'connected',
                        'host': self.host,
                        'port': self.port,
                        'timestamp': time.time()
                    })

                # 启动网络状态更新线程
                self.running = True
                self.status_update_thread = threading.Thread(target=self._status_update_loop)
                self.status_update_thread.daemon = True
                self.status_update_thread.start()

                logger.info("已连接到服务器，等待数据...")

                # 保持连接
                while self.connected:
                    await asyncio.sleep(1)

        except Exception as e:
            logger.error(f"连接错误: {e}")
            self.connected = False

            if self.connection_status_callback:
                self.connection_status_callback({
                    'status': 'error',
                    'error': str(e),
                    'timestamp': time.time()
                })
    def _session_ticket_handler(self, ticket):
        """处理会话票据"""
        logger.debug("收到会话票据")

    def _quic_logger(self, event: Dict[str, Any]):
        """QUIC事件日志处理"""
        # 提取RTT信息
        if event.get('category') == 'recovery':
            details = event.get('data', {})
            if 'latest_rtt' in details:
                rtt = details['latest_rtt'] * 1000  # 转换为毫秒
                self.last_rtt_samples.append(rtt)

                # 保持样本数量合理
                if len(self.last_rtt_samples) > 10:
                    self.last_rtt_samples.pop(0)

                # 更新平均RTT
                self.stats['rtt'] = sum(self.last_rtt_samples) / len(self.last_rtt_samples)

    def _on_video_frame(self, frame_data: bytes, frame_info: Dict[str, Any]):
        """
        视频帧回调

        Args:
            frame_data: 帧数据
            frame_info: 帧信息
        """
        # 更新统计信息
        self.stats['bytes_received'] += len(frame_data)
        self.stats['packets_received'] += 1

        # 计算带宽(bps)
        elapsed = time.time() - self.stats['connected_at']
        if elapsed > 0:
            current_bandwidth = self.stats['bytes_received'] * 8 / elapsed
            self.last_bandwidth_samples.append(current_bandwidth)

            # 保持样本数量合理
            if len(self.last_bandwidth_samples) > 10:
                self.last_bandwidth_samples.pop(0)

            # 更新平均带宽
            self.stats['bandwidth'] = sum(self.last_bandwidth_samples) / len(self.last_bandwidth_samples)

        # 将帧放入队列
        try:
            if not self.video_queue.full():
                self.video_queue.put((frame_data, frame_info), block=False)
            else:
                logger.warning("视频队列已满，丢弃帧")
        except queue.Full:
            logger.warning("视频队列已满，丢弃帧")

        # 如果设置了回调，调用回调
        if self.video_frame_callback:
            self.video_frame_callback(frame_data, frame_info)

    def _status_update_loop(self):
        """网络状态更新循环"""
        while self.running and self.connected:
            try:
                # 每秒更新一次网络状态
                time.sleep(1)

                # 创建状态消息
                status = {
                    'type': 'status',
                    'timestamp': time.time(),
                    'rtt': self.stats['rtt'],
                    'packet_loss': self.stats['packet_loss'],
                    'bandwidth': self.stats['bandwidth']
                }

                # 发送状态更新
                if self.connection:
                    self._send_status_update(status)

                self.stats['last_status_update'] = time.time()

            except Exception as e:
                logger.error(f"状态更新错误: {e}")

    def _send_status_update(self, status: Dict[str, Any]):
        """
        发送状态更新到服务器

        Args:
            status: 状态信息
        """
        try:
            # 序列化状态消息
            message = json.dumps(status).encode('utf-8')

            # 获取一个新的流ID
            stream_id = self.connection._quic.get_next_available_stream_id()

            # 发送数据
            self.connection._quic.send_stream_data(stream_id, message)

            logger.debug(f"已发送状态更新: RTT={status['rtt']:.2f}ms, 带宽={status['bandwidth'] / 1000:.2f}Kbps")

        except Exception as e:
            logger.error(f"发送状态更新错误: {e}")

    def set_video_frame_callback(self, callback: Callable[[bytes, Dict[str, Any]], None]):
        """
        设置视频帧回调

        Args:
            callback: 回调函数(frame_data, frame_info) -> None
        """
        self.video_frame_callback = callback

    def set_connection_status_callback(self, callback: Callable[[Dict[str, Any]], None]):
        """
        设置连接状态回调

        Args:
            callback: 回调函数(status_info) -> None
        """
        self.connection_status_callback = callback

    def get_next_video_frame(self, timeout: float = 1.0) -> Optional[Tuple[bytes, Dict[str, Any]]]:
        """
        从队列获取下一个视频帧

        Args:
            timeout: 超时时间(秒)

        Returns:
            (帧数据, 帧信息)的元组，如果超时则返回None
        """
        try:
            return self.video_queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def get_connection_stats(self) -> Dict[str, Any]:
        """
        获取连接统计信息

        Returns:
            连接统计信息字典
        """
        return self.stats.copy()

    def disconnect(self):
        """断开连接"""
        logger.info("断开连接")
        self.running = False
        self.connected = False

        if self.connection:
            self.connection.close()
            self.connection = None

        if self.status_update_thread and self.status_update_thread.is_alive():
            self.status_update_thread.join(timeout=2.0)

        if self.connection_status_callback:
            self.connection_status_callback({
                'status': 'disconnected',
                'timestamp': time.time()
            })


class QuicClientProtocol(QuicConnectionProtocol):
    """
    QUIC客户端协议处理器
    处理QUIC事件和数据流
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.video_frame_callback = None
        self._packets_buffer = {}  # 用于重组分片的包
        self._quic_logger = None
        self._stream_buffer = {}   # 新增：每个流ID的缓冲区

    def connection_made(self, transport):
        logger.info("连接已建立")
        super().connection_made(transport)

    def connection_lost(self, exc):
        logger.info(f"连接已断开: {exc}")
        super().connection_lost(exc)

    def quic_event_received(self, event: QuicEvent):
        """处理QUIC事件"""
        logger.info(f"收到QUIC事件: {type(event).__name__}")
        if isinstance(event, StreamDataReceived):
            logger.info(f"收到流数据: {len(event.data)} 字节, 流ID: {event.stream_id}")
            self._handle_stream_data(event.stream_id, event.data, event.end_stream)
        else:
            super().quic_event_received(event)

    def _handle_stream_data(self, stream_id: int, data: bytes, end_stream: bool):
        """
        处理接收到的流数据

        Args:
            stream_id: 流ID
            data: 接收到的数据
            end_stream: 是否是流的结束
        """
        logger.info(f"处理流数据: {len(data)} 字节")

        # 累加到流缓冲
        buf = self._stream_buffer.setdefault(stream_id, b'') + data

        offset = 0
        while True:
            if offset + 4 > len(buf):
                break
            try:
                header_len = struct.unpack('!I', buf[offset:offset+4])[0]
                if header_len > 10000 or offset + 4 + header_len > len(buf):
                    break
                header_json = buf[offset+4:offset+4+header_len]
                header = json.loads(header_json.decode('utf-8'))
                data_size = header.get('data_size', 0)
                if offset + 4 + header_len + data_size > len(buf):
                    break
                frame_data = buf[offset+4+header_len : offset+4+header_len+data_size]
                if header.get('type') == 'video_data':
                    logger.info(f"收到视频数据: 帧ID {header.get('frame_id', 'unknown')}, {len(frame_data)} 字节")
                    if self.video_frame_callback:
                        self.video_frame_callback(frame_data, header)
                else:
                    logger.debug(f"收到非视频数据: {header.get('type', 'unknown')}")
                offset += 4 + header_len + data_size
            except Exception as e:
                logger.error(f"解析视频包异常: {e}")
                break
        # 剩余未处理的部分保留到下次
        self._stream_buffer[stream_id] = buf[offset:]