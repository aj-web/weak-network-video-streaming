import asyncio
import logging
import os
import sys
import time
import threading
from queue import Queue

# 修复：将项目根目录添加到Python路径，必须在所有自定义模块导入之前
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import numpy as np
from client.video.decoder import VideoDecoder
from client.video.renderer import VideoRenderer
from client.network.quic_client import VideoStreamClient

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("client_test")

# 用于存储接收到的视频帧
received_frames = Queue()

decoder = VideoDecoder()
renderer = VideoRenderer()

# 网络回调只负责入队
def on_video_frame(frame_data, frame_info):
    logger.info(f"收到视频帧: {len(frame_data)} 字节, 帧ID: {frame_info.get('frame_id', 'unknown')}")
    received_frames.put((frame_data, frame_info))
    # 自动保存原始帧数据
    try:
        with open('recv_test.h264', 'ab') as f:
            f.write(frame_data)
    except Exception as e:
        logger.error(f"保存帧数据失败: {e}")

# 渲染线程：解码并显示
def render_loop():
    while True:
        try:
            frame_data, frame_info = received_frames.get(timeout=1.0)
            img = decoder.decode(frame_data)
            if img is not None:
                renderer.render(img)
            received_frames.task_done()
        except Exception:
            pass  # 可加退出条件

# 连接状态回调
def on_connection_status(status):
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

    # 启动渲染线程
    render_thread = threading.Thread(target=render_loop, daemon=True)
    render_thread.start()

    try:
        logger.info(f"连接到服务器: {client.host}:{client.port}")
        await client.connect()
        # 保持主线程活跃，防止窗口假死
        while True:
            await asyncio.sleep(10)
    except KeyboardInterrupt:
        logger.info("用户中断")
    except Exception as e:
        logger.error(f"错误: {e}")
    finally:
        client.disconnect()
        logger.info("已断开连接")

if __name__ == "__main__":
    # 运行主函数
    asyncio.run(main())