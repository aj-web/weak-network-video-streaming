import asyncio
import logging
import os
import sys
import time
import threading
from queue import Queue

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from client.network.quic_client import VideoStreamClient

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("client_test")

# 用于存储接收到的视频帧
received_frames = Queue()


def on_video_frame(frame_data, frame_info):
    """视频帧回调"""
    logger.info(f"收到视频帧: {len(frame_data)} 字节, 帧ID: {frame_info.get('frame_id', 'unknown')}")
    received_frames.put((frame_data, frame_info))


def on_connection_status(status):
    """连接状态回调"""
    logger.info(f"连接状态更新: {status['status']}")


async def main():
    """主函数"""
    # 创建客户端
    client = VideoStreamClient(
        host="127.0.0.1",  # 修改为服务器IP
        port=4433,
        verify_ssl=False
    )

    # 设置回调
    client.set_video_frame_callback(on_video_frame)
    client.set_connection_status_callback(on_connection_status)

    # 显示接收数据的线程
    def show_received_data():
        frame_count = 0
        start_time = time.time()

        while True:
            try:
                frame_data, frame_info = received_frames.get(timeout=1.0)
                frame_count += 1

                # 每10帧显示一次统计信息
                if frame_count % 10 == 0:
                    elapsed = time.time() - start_time
                    if elapsed > 0:
                        fps = frame_count / elapsed
                        logger.info(f"已接收 {frame_count} 帧, 平均 {fps:.2f} fps")

                # 可以在这里添加代码来处理和显示帧数据
                # 例如: 保存到文件、解码为图像等

                received_frames.task_done()
            except:
                # 超时或队列为空
                if not client.connected:
                    break

    # 启动显示线程
    display_thread = threading.Thread(target=show_received_data)
    display_thread.daemon = True
    display_thread.start()

    try:
        # 连接到服务器
        logger.info(f"连接到服务器: {client.host}:{client.port}")
        await client.connect()

        # 等待用户中断
        while client.connected:
            # 每5秒显示一次网络统计信息
            stats = client.get_connection_stats()
            logger.info(
                f"网络统计: RTT={stats['rtt']:.2f}ms, 带宽={stats['bandwidth'] / 1000000:.2f}Mbps, 接收={stats['bytes_received'] / 1024:.2f}KB")

            await asyncio.sleep(5)

    except KeyboardInterrupt:
        logger.info("用户中断")
    except Exception as e:
        logger.error(f"错误: {e}")
    finally:
        # 断开连接
        client.disconnect()
        logger.info("已断开连接")


if __name__ == "__main__":
    # 运行主函数
    asyncio.run(main())