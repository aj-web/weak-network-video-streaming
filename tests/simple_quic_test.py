# simple_quic_test.py
import asyncio
import logging
import ssl
from aioquic.asyncio import connect
from aioquic.asyncio.protocol import QuicConnectionProtocol
from aioquic.quic.configuration import QuicConfiguration
from aioquic.quic.events import QuicEvent, StreamDataReceived

# 配置日志
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("simple_quic_test")


class SimpleQuicProtocol(QuicConnectionProtocol):
    def connection_made(self, transport):
        logger.info("连接已建立")
        super().connection_made(transport)

        # 发送测试数据
        stream_id = self._quic.get_next_available_stream_id()
        self._quic.send_stream_data(stream_id, b"Hello, server!")
        logger.info(f"已发送测试数据到流 {stream_id}")

    def connection_lost(self, exc):
        logger.info(f"连接已断开: {exc}")
        super().connection_lost(exc)

    def quic_event_received(self, event: QuicEvent):
        logger.info(f"收到QUIC事件: {type(event).__name__}")
        if isinstance(event, StreamDataReceived):
            logger.info(f"收到流数据: {event.data.decode(errors='ignore')}")
        super().quic_event_received(event)


async def main():
    # 创建QUIC配置
    configuration = QuicConfiguration(
        alpn_protocols=["video-streaming"],
        is_client=True,
        verify_mode=ssl.CERT_NONE
    )

    logger.info("连接到服务器: 127.0.0.1:4433")

    try:
        async with connect(
                "127.0.0.1",
                4433,
                configuration=configuration,
                create_protocol=SimpleQuicProtocol,
                wait_connected=True
        ) as client:
            logger.info("等待数据...")
            await asyncio.sleep(30)  # 等待30秒

    except Exception as e:
        logger.error(f"连接错误: {e}", exc_info=True)


if __name__ == "__main__":
    asyncio.run(main())