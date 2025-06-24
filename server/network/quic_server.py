import asyncio
import logging
import os
import ssl
import time
from typing import Dict, Any, Optional, List, Callable
import json
import struct

from aioquic.asyncio import serve, QuicConnectionProtocol
from aioquic.quic.configuration import QuicConfiguration
from aioquic.quic.events import QuicEvent, StreamDataReceived
from aioquic.quic.logger import QuicFileLogger

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("quic_server")


class VideoStreamProtocol:
    """
    使用QUIC协议的视频流传输协议
    负责处理视频数据包的发送和接收网络状态反馈
    """

    def __init__(self):
        """初始化协议处理器"""
        # 连接管理
        self.connections = {}

        # 数据包序列号
        self.next_packet_id = 0

        # 网络状态回调
        self.network_status_callback = None

    def connection_made(self, connection_id):
        """新连接建立时调用"""
        logger.info(f"新建连接: {connection_id}")
        self.connections[connection_id] = {
            'id': connection_id,
            'connected_at': time.time(),
            'last_active': time.time(),
            'bytes_sent': 0,
            'packets_sent': 0,
            'rtt': 0,
            'packet_loss': 0,
            'bandwidth': 0
        }

    def connection_lost(self, connection_id):
        """连接断开时调用"""
        if connection_id in self.connections:
            logger.info(f"连接断开: {connection_id}")
            del self.connections[connection_id]

    def process_stream_data(self, connection_id, stream_id, data):
        """处理从客户端接收的流数据"""
        try:
            # 解析数据(通常是网络状态反馈)
            message = json.loads(data.decode('utf-8'))

            if message.get('type') == 'status':
                # 更新连接状态
                conn_state = self.connections.get(connection_id)
                if conn_state:
                    conn_state['last_active'] = time.time()
                    conn_state['rtt'] = message.get('rtt', 0)
                    conn_state['packet_loss'] = message.get('packet_loss', 0)
                    conn_state['bandwidth'] = message.get('bandwidth', 0)

                    # 调用网络状态回调(如果设置了)
                    if self.network_status_callback:
                        self.network_status_callback(conn_state)

                    logger.debug(
                        f"收到网络状态: RTT={conn_state['rtt']}ms, 丢包率={conn_state['packet_loss']}%, 带宽={conn_state['bandwidth'] / 1000}Kbps")

            # 回复确认
            return {'type': 'ack', 'timestamp': time.time()}

        except Exception as e:
            logger.error(f"处理流数据错误: {e}")
            return {'type': 'error', 'message': str(e)}

    def create_video_packet(self, frame_data, frame_info=None):
        """
        创建视频数据包

        Args:
            frame_data: 编码后的视频帧数据
            frame_info: 帧相关信息

        Returns:
            格式化的数据包
        """
        packet_id = self.next_packet_id
        self.next_packet_id += 1

        timestamp = int(time.time() * 1000)  # 毫秒时间戳

        # 默认帧信息
        if frame_info is None:
            frame_info = {}

        # 创建数据包头部
        header = {
            'id': packet_id,
            'timestamp': timestamp,
            'keyframe': frame_info.get('keyframe', False),
            'width': frame_info.get('width', 0),
            'height': frame_info.get('height', 0),
            'data_size': len(frame_data)
        }

        # 序列化头部
        header_json = json.dumps(header).encode('utf-8')

        # 创建包含头部长度的数据包
        header_len = len(header_json)
        packet = struct.pack('!I', header_len) + header_json + frame_data

        return packet, header

    def set_network_status_callback(self, callback: Callable[[Dict[str, Any]], None]):
        """设置网络状态更新回调"""
        self.network_status_callback = callback

    def get_connection_stats(self) -> Dict[str, Any]:
        """获取所有连接的统计信息"""
        stats = {
            'connections': len(self.connections),
            'total_bytes_sent': sum(conn['bytes_sent'] for conn in self.connections.values()),
            'total_packets_sent': sum(conn['packets_sent'] for conn in self.connections.values()),
            'connection_details': list(self.connections.values())
        }
        return stats


class QuicServer:
    """
    QUIC协议服务器，用于低延迟视频传输
    """

    def __init__(self,
                 host: str = "0.0.0.0",
                 port: int = 4433,
                 cert_file: str = None,
                 key_file: str = None):
        """
        初始化QUIC服务器

        Args:
            host: 监听地址
            port: 监听端口
            cert_file: SSL证书文件路径
            key_file: SSL私钥文件路径
        """
        self.host = host
        self.port = port
        self.cert_file = cert_file
        self.key_file = key_file

        # 如果没有提供证书和密钥，使用自签名证书
        if not cert_file or not key_file:
            self._generate_self_signed_cert()

        # 视频流协议处理器
        self.protocol = VideoStreamProtocol()

        # 服务器状态
        self.running = False
        self.server = None

    def _generate_self_signed_cert(self):
        """使用Python生成自签名证书(不依赖外部OpenSSL)"""
        import tempfile
        from cryptography import x509
        from cryptography.x509.oid import NameOID
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.hazmat.primitives import serialization
        import datetime

        logger.info("使用Python生成自签名证书...")

        # 创建临时目录
        cert_dir = tempfile.mkdtemp()
        self.cert_file = os.path.join(cert_dir, "cert.pem")
        self.key_file = os.path.join(cert_dir, "key.pem")

        try:
            # 生成私钥
            private_key = rsa.generate_private_key(
                public_exponent=65537,
                key_size=2048
            )

            # 创建自签名证书
            subject = issuer = x509.Name([
                x509.NameAttribute(NameOID.COMMON_NAME, "localhost")
            ])

            cert = x509.CertificateBuilder().subject_name(
                subject
            ).issuer_name(
                issuer
            ).public_key(
                private_key.public_key()
            ).serial_number(
                x509.random_serial_number()
            ).not_valid_before(
                datetime.datetime.utcnow()
            ).not_valid_after(
                datetime.datetime.utcnow() + datetime.timedelta(days=365)
            ).add_extension(
                x509.SubjectAlternativeName([x509.DNSName("localhost")]),
                critical=False
            ).sign(private_key, hashes.SHA256())

            # 保存私钥
            with open(self.key_file, "wb") as f:
                f.write(private_key.private_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PrivateFormat.PKCS8,
                    encryption_algorithm=serialization.NoEncryption()
                ))

            # 保存证书
            with open(self.cert_file, "wb") as f:
                f.write(cert.public_bytes(serialization.Encoding.PEM))

            logger.info(f"自签名证书已生成: {self.cert_file}")

        except Exception as e:
            logger.error(f"生成证书失败: {e}")
            raise RuntimeError("无法生成自签名证书")

    async def start(self):
        """启动QUIC服务器"""
        if self.running:
            logger.warning("服务器已经在运行")
            return

        # QUIC配置
        quic_config = QuicConfiguration(
            alpn_protocols=["video-streaming"],
            is_client=False,
            max_datagram_frame_size=65536
        )

        # 设置SSL证书
        quic_config.load_cert_chain(self.cert_file, self.key_file)

        # 创建协议工厂
        protocol = self.protocol  # 保存对协议处理器的引用

        def create_protocol(*args, **kwargs):
            return QuicServerHandler(*args, protocol=protocol, **kwargs)

        # 启动服务器
        self.server = await serve(
            self.host,
            self.port,
            configuration=quic_config,
            create_protocol=create_protocol,
            retry=True
        )

        self.running = True
        logger.info(f"QUIC服务器已启动: {self.host}:{self.port}")

        # 保持运行
        while self.running:
            await asyncio.sleep(1)
    def send_video_packet(self, connection_id, frame_data, frame_info=None):
        """
        向指定连接发送视频包

        Args:
            connection_id: 连接ID
            frame_data: 编码后的视频帧数据
            frame_info: 帧相关信息
        """
        # 实际实现将在QuicServerHandler中
        pass

    def broadcast_video_packet(self, frame_data, frame_info=None):
        """
        向所有连接广播视频包

        Args:
            frame_data: 编码后的视频帧数据
            frame_info: 帧相关信息
        """
        # 实际实现将在QuicServerHandler中
        pass

    def set_network_status_callback(self, callback: Callable[[Dict[str, Any]], None]):
        """设置网络状态更新回调"""
        self.protocol.set_network_status_callback(callback)

    def get_connection_stats(self) -> Dict[str, Any]:
        """获取连接统计信息"""
        return self.protocol.get_connection_stats()


class QuicServerHandler(QuicConnectionProtocol):
    """
    QUIC服务器处理程序，管理QUIC事件和数据流
    """

    def __init__(self, *args, **kwargs):
        self.protocol = kwargs.pop('protocol', None)
        super().__init__(*args, **kwargs)
        self.connection_id = None

    def connection_made(self, transport):
        """连接建立时调用"""
        super().connection_made(transport)
        self.connection_id = str(id(self))
        if self.protocol:
            self.protocol.connection_made(self.connection_id)
        logger.info(f"建立新连接: {self.connection_id}")

    def connection_lost(self, exc):
        """连接断开时调用"""
        logger.info(f"连接断开: {self.connection_id}, 原因: {exc}")
        if self.protocol:
            self.protocol.connection_lost(self.connection_id)
        super().connection_lost(exc)

    def quic_event_received(self, event: QuicEvent):
        """处理QUIC事件"""
        logger.debug(f"收到QUIC事件: {type(event).__name__}")

        if isinstance(event, StreamDataReceived) and self.protocol:
            # 处理客户端发送的数据
            response = self.protocol.process_stream_data(
                self.connection_id,
                event.stream_id,
                event.data
            )

            # 如果有响应，发送回客户端
            if response:
                self._quic.send_stream_data(
                    event.stream_id,
                    json.dumps(response).encode('utf-8')
                )
        else:
            super().quic_event_received(event)

    def send_video_packet(self, frame_data, frame_info=None):
        """
        发送视频数据包

        Args:
            frame_data: 编码后的视频帧数据
            frame_info: 帧相关信息
        """
        if not self.quic:
            return False

        # 创建视频数据包
        packet, header = self.protocol.create_video_packet(frame_data, frame_info)

        # 发送数据包
        stream_id = self.quic.get_next_available_stream_id()
        self.quic.send_stream_data(stream_id, packet)

        # 更新统计信息
        if self.connection_id in self.protocol.connections:
            conn_state = self.protocol.connections[self.connection_id]
            conn_state['last_active'] = time.time()
            conn_state['bytes_sent'] += len(packet)
            conn_state['packets_sent'] += 1

        return True