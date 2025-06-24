# simple_quic_server.py
import asyncio
import logging
import os
import tempfile
from typing import Dict, Any, Optional, Tuple
import datetime

from aioquic.asyncio import serve
from aioquic.asyncio.protocol import QuicConnectionProtocol
from aioquic.quic.configuration import QuicConfiguration
from aioquic.quic.events import QuicEvent, StreamDataReceived

# 用于证书生成
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization

# 配置日志
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("simple_quic_server")


class SimpleQuicServerProtocol(QuicConnectionProtocol):
    def connection_made(self, transport):
        logger.info("建立新连接")
        super().connection_made(transport)

    def connection_lost(self, exc):
        logger.info(f"连接断开: {exc}")
        super().connection_lost(exc)

    def quic_event_received(self, event: QuicEvent):
        logger.info(f"收到QUIC事件: {type(event).__name__}")

        if isinstance(event, StreamDataReceived):
            logger.info(f"收到流数据: {event.data.decode(errors='ignore')}")

            # 回复客户端
            self._quic.send_stream_data(
                event.stream_id,
                f"收到你的消息: {event.data.decode(errors='ignore')}".encode()
            )
        else:
            super().quic_event_received(event)


def generate_self_signed_cert() -> Tuple[str, str]:
    """使用Python生成自签名证书"""
    logger.info("使用Python生成自签名证书...")

    # 创建临时目录
    cert_dir = tempfile.mkdtemp()
    cert_file = os.path.join(cert_dir, "cert.pem")
    key_file = os.path.join(cert_dir, "key.pem")

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
        with open(key_file, "wb") as f:
            f.write(private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            ))

        # 保存证书
        with open(cert_file, "wb") as f:
            f.write(cert.public_bytes(serialization.Encoding.PEM))

        logger.info(f"自签名证书已生成: {cert_file}")
        return cert_file, key_file

    except Exception as e:
        logger.error(f"生成证书失败: {e}")
        raise RuntimeError("无法生成自签名证书")


async def main():
    # 生成证书
    cert_file, key_file = generate_self_signed_cert()

    # QUIC配置
    configuration = QuicConfiguration(
        alpn_protocols=["video-streaming"],
        is_client=False,
        max_datagram_frame_size=65536
    )

    # 设置SSL证书
    configuration.load_cert_chain(cert_file, key_file)

    # 启动服务器
    logger.info("启动QUIC服务器: 0.0.0.0:4433")

    server = await serve(
        "0.0.0.0",
        4433,
        configuration=configuration,
        create_protocol=SimpleQuicServerProtocol
    )

    logger.info("服务器已启动，等待连接...")

    # 保持运行
    await asyncio.Future()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("服务器已停止")