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

    def connection_made(self, connection_id, handler=None):
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
            'bandwidth': 0,
            'handler': handler  # 保存handler实例
        }

        # 输出当前连接数
        logger.info(f"当前连接数: {len(self.connections)}")

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
            'data_size': len(frame_data),
            'type': 'video_data'  # 添加类型字段
        }

        # 序列化头部
        header_json = json.dumps(header).encode('utf-8')

        # 创建包含头部长度的数据包
        header_len = len(header_json)
        # 确保头部长度以网络字节序（大端）编码
        packet = struct.pack('!I', header_len) + header_json + frame_data

        logger.debug(f"创建数据包: 头部 {header_len} 字节, 数据 {len(frame_data)} 字节, 总计 {len(packet)} 字节")

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

    def broadcast_video_frame(self, frame_data, frame_info=None):
        """
        广播视频帧到所有连接的客户端

        Args:
            frame_data: 视频帧数据
            frame_info: 帧信息
        """
        logger.info(f"协议广播视频帧: {len(frame_data)} 字节, 连接数: {len(self.connections)}")

        if not self.connections:
            logger.warning("没有活跃连接，无法广播视频帧")
            return

        # 如果没有提供帧信息，创建一个默认的
        if frame_info is None:
            frame_info = {}

        # 确保帧信息包含必要的字段
        if 'type' not in frame_info:
            frame_info['type'] = 'video_data'
        if 'frame_id' not in frame_info:
            frame_info['frame_id'] = self.next_packet_id
            self.next_packet_id += 1
        if 'timestamp' not in frame_info:
            frame_info['timestamp'] = int(time.time() * 1000)

        # 如果是纯文本数据，直接发送
        if frame_info.get('type') == 'test_data' and isinstance(frame_data, bytes):
            for conn_id, conn_data in self.connections.items():
                try:
                    handler = conn_data.get('handler')
                    if handler and hasattr(handler, 'send_packet'):
                        logger.info(f"发送测试数据到连接 {conn_id}")
                        success = handler.send_packet(frame_data)
                        if success:
                            logger.info(f"成功发送测试数据到连接 {conn_id}")
                        else:
                            logger.warning(f"发送测试数据到连接 {conn_id} 失败")
                    else:
                        logger.warning(f"连接 {conn_id} 没有有效的处理程序")
                except Exception as e:
                    logger.error(f"发送测试数据到连接 {conn_id} 异常: {e}")
            return

        # 创建视频数据包
        try:
            packet, header = self.create_video_packet(frame_data, frame_info)
            logger.info(f"创建视频数据包: {len(packet)} 字节, 帧ID: {header.get('frame_id', 'unknown')}")

            # 广播到所有连接
            for conn_id, conn_data in self.connections.items():
                try:
                    handler = conn_data.get('handler')
                    if handler and hasattr(handler, 'send_packet'):
                        logger.info(f"发送视频帧到连接 {conn_id}")
                        success = handler.send_packet(packet)
                        if success:
                            logger.info(f"成功发送视频帧到连接 {conn_id}")
                        else:
                            logger.warning(f"发送视频帧到连接 {conn_id} 失败")
                    else:
                        logger.warning(f"连接 {conn_id} 没有有效的处理程序")
                except Exception as e:
                    logger.error(f"发送视频帧到连接 {conn_id} 异常: {e}")
                    import traceback
                    traceback.print_exc()
        except Exception as e:
            logger.error(f"创建视频数据包失败: {e}")
            import traceback
            traceback.print_exc()


    def broadcast_test_message(self, message_data):
        """
        广播测试消息到所有连接的客户端

        Args:
            message_data: 消息数据(JSON编码的字节)
        """
        logger.info(f"广播测试消息: {len(message_data)} 字节, 连接数: {len(self.connections)}")

        if not self.connections:
            logger.warning("没有活跃连接，无法广播测试消息")
            return

        # 广播到所有连接
        for conn_id, conn_data in self.connections.items():
            try:
                handler = conn_data.get('handler')
                if handler and hasattr(handler, 'send_packet'):
                    logger.info(f"发送测试消息到连接 {conn_id}")
                    success = handler.send_packet(message_data)
                    if success:
                        logger.info(f"成功发送测试消息到连接 {conn_id}")
                    else:
                        logger.warning(f"发送测试消息到连接 {conn_id} 失败")
                else:
                    logger.warning(f"连接 {conn_id} 没有有效的处理程序")
            except Exception as e:
                logger.error(f"发送测试消息到连接 {conn_id} 异常: {e}")
                import traceback
                traceback.print_exc()


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
            # 使用类变量保存协议处理器
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

    def broadcast_video_frame(self, frame_data, frame_info=None):
        """
        广播视频帧到所有连接的客户端

        Args:
            frame_data: 视频帧数据
            frame_info: 帧信息
        """
        logger.info(f"广播视频帧: {len(frame_data)} 字节")
        self.protocol.broadcast_video_frame(frame_data, frame_info)


class QuicServerHandler(QuicConnectionProtocol):
    """
    QUIC服务器处理程序，管理QUIC事件和数据流
    """

    def __init__(self, *args, **kwargs):
        # 将 protocol 保存为类变量，而不是从 kwargs 中弹出
        self.video_protocol = kwargs.pop('protocol', None)
        super().__init__(*args, **kwargs)
        self.connection_id = str(id(self))
        logger.debug(f"创建新的QuicServerHandler: {self.connection_id}")

    def connection_made(self, transport):
        """连接建立时调用"""
        logger.info(f"连接建立: {self.connection_id}")
        super().connection_made(transport)

        # 通知协议处理器
        if self.video_protocol:
            self.video_protocol.connection_made(self.connection_id, self)
        else:
            logger.error("视频协议处理器为空")

    def connection_lost(self, exc):
        """连接断开时调用"""
        logger.info(f"连接断开: {self.connection_id}, 原因: {exc}")

        # 通知协议处理器
        if self.video_protocol:
            self.video_protocol.connection_lost(self.connection_id)

        super().connection_lost(exc)

    def quic_event_received(self, event: QuicEvent):
        """处理QUIC事件"""
        logger.debug(f"收到QUIC事件: {type(event).__name__}")

        if isinstance(event, StreamDataReceived) and self.video_protocol:
            logger.info(f"收到流数据: {len(event.data)} 字节, 流ID: {event.stream_id}")

            # 处理客户端发送的数据
            response = self.video_protocol.process_stream_data(
                self.connection_id,
                event.stream_id,
                event.data
            )

            # 如果有响应，发送回客户端
            if response:
                logger.info(f"发送响应: {len(json.dumps(response).encode('utf-8'))} 字节, 流ID: {event.stream_id}")
                self._quic.send_stream_data(
                    event.stream_id,
                    json.dumps(response).encode('utf-8')
                )
        else:
            super().quic_event_received(event)

    def send_packet(self, packet):
        """
        发送数据包到客户端

        Args:
            packet: 要发送的数据包

        Returns:
            是否成功发送
        """
        try:
            if self._quic:
                stream_id = self._quic.get_next_available_stream_id()
                self._quic.send_stream_data(stream_id, packet)
                logger.info(f"发送数据包: {len(packet)} 字节, 流ID: {stream_id}")
                return True
            else:
                logger.warning("QUIC连接不可用")
                return False
        except Exception as e:
            logger.error(f"发送数据包异常: {e}")
            return False