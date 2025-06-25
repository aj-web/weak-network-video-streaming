import asyncio
import argparse
import json
import logging
import queue
import signal
import threading
import time
import os
import sys
from typing import Dict, Any

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from server.screen_capture import ScreenCapturer
from server.roi_detector import ROIDetector
from server.video_encoder import VideoEncoder
from server.network.quic_server import QuicServer

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("main")


class VideoStreamingServer:
    """
    视频流服务端主类，协调各模块工作
    """

    def __init__(self,
                 host: str = "0.0.0.0",
                 port: int = 4433,
                 fps: int = 30,
                 bitrate: int = 3000000,
                 use_roi: bool = True):
        """
        初始化视频流服务端

        Args:
            host: 监听地址
            port: 监听端口
            fps: 目标帧率
            bitrate: 初始码率
            use_roi: 是否启用ROI编码
        """
        self.host = host
        self.port = port
        self.fps = fps
        self.bitrate = bitrate
        self.use_roi = use_roi

        # 状态变量
        self.running = False
        self.loop = None
        self.main_thread = None

        # 初始化各模块
        self._initialize_modules()

    def _initialize_modules(self):
        """初始化各功能模块"""
        # 屏幕捕获模块
        self.screen_capturer = ScreenCapturer(capture_rate=self.fps)

        # 获取屏幕尺寸
        self.width, self.height = self.screen_capturer.get_monitor_size()

        # ROI检测模块
        self.roi_detector = ROIDetector(
            frame_width=self.width,
            frame_height=self.height
        )

        # 定义编码帧回调
        def on_frame_encoded(frame_data, frame_info):
            logger.info(f"编码帧回调: {len(frame_data)} 字节")
            # 广播视频帧到所有客户端
            try:
                self.quic_server.broadcast_video_frame(frame_data, frame_info)
            except Exception as e:
                logger.error(f"广播视频帧异常: {e}")
                import traceback
                traceback.print_exc()

        # 视频编码模块
        self.video_encoder = VideoEncoder(
            width=self.width,
            height=self.height,
            fps=self.fps,
            bitrate=self.bitrate,
            use_roi=self.use_roi,
            frame_callback=on_frame_encoded
        )

        # QUIC服务器
        self.quic_server = QuicServer(host=self.host, port=self.port)

        # 设置网络状态回调
        self.quic_server.set_network_status_callback(self._on_network_status_update)

        logger.info(f"初始化完成: 分辨率={self.width}x{self.height}, FPS={self.fps}, 码率={self.bitrate / 1000000}Mbps")

    def _on_network_status_update(self, network_status: Dict[str, Any]):
        """
        网络状态更新回调

        Args:
            network_status: 网络状态信息
        """
        # 提取网络状态信息
        rtt = network_status.get('rtt', 0)
        packet_loss = network_status.get('packet_loss', 0)
        bandwidth = network_status.get('bandwidth', 0)

        logger.debug(f"网络状态更新: RTT={rtt}ms, 丢包率={packet_loss}%, 带宽={bandwidth / 1000000}Mbps")

        # 根据网络状态调整编码参数
        self._adjust_encoding_params(rtt, packet_loss, bandwidth)

    def _adjust_encoding_params(self, rtt: float, packet_loss: float, bandwidth: float):
        """
        根据网络状态调整编码参数

        Args:
            rtt: 往返时间(ms)
            packet_loss: 丢包率(%)
            bandwidth: 带宽(bps)
        """
        # 简单的自适应码率策略

        # 根据带宽调整码率
        if bandwidth > 0:
            # 使用带宽的80%作为视频码率
            target_bitrate = int(bandwidth * 0.8)

            # 设置合理的上下限
            target_bitrate = max(500000, min(target_bitrate, 10000000))

            # 调整编码器码率
            self.video_encoder.adjust_bitrate(target_bitrate)

        # 根据丢包率调整GOP大小
        if packet_loss > 5.0:
            # 高丢包率时使用更小的GOP
            self.video_encoder.adjust_gop_size(15)
        elif packet_loss > 2.0:
            self.video_encoder.adjust_gop_size(20)
        else:
            # 低丢包率时使用标准GOP
            self.video_encoder.adjust_gop_size(30)

        # 如果RTT很高，可以考虑降低帧率
        # (这需要修改屏幕捕获模块的帧率)

    async def _run_quic_server(self):
        """启动QUIC服务器(异步)"""
        await self.quic_server.start()

    def _main_loop(self):
        """主循环，处理屏幕捕获、编码和发送"""
        logger.info("启动主循环")

        self.screen_capturer.start()
        self.video_encoder.start()

        try:
            count = 0
            while self.running:
                # 捕获屏幕
                frame = self.screen_capturer.capture_frame()

                # 获取鼠标位置
                mouse_pos = self.screen_capturer.get_mouse_position()

                # 检测ROI
                roi_info = self.roi_detector.detect_roi(frame, mouse_pos)

                # 编码帧
                self.video_encoder.encode_frame(frame, roi_info)

                # 每隔5帧发送一次测试数据
                count += 1
                if count % 5 == 0:
                    try:
                        # 向所有连接的客户端发送测试数据
                        test_message = {
                            'type': 'test_data',
                            'timestamp': int(time.time() * 1000),
                            'message': f'Test message #{count}'
                        }

                        # 使用JSON格式发送
                        json_data = json.dumps(test_message).encode('utf-8')
                        logger.info(f"发送测试数据: {len(json_data)} 字节, 消息: {test_message['message']}")

                        # 修复：调用 broadcast_test_message，避免协议混用
                        self.quic_server.protocol.broadcast_test_message(json_data)
                    except Exception as e:
                        logger.error(f"发送测试数据异常: {e}")
                        import traceback
                        traceback.print_exc()

                # 控制循环速率
                time.sleep(1.0 / self.fps)

        except KeyboardInterrupt:
            logger.info("接收到用户中断")
        except Exception as e:
            logger.error(f"主循环异常: {e}", exc_info=True)
        finally:
            # 停止各模块
            self.screen_capturer.stop()
            self.video_encoder.stop()

    def start(self):
        """启动服务器"""
        if self.running:
            logger.warning("服务器已经在运行")
            return

        logger.info(f"启动视频流服务器: {self.host}:{self.port}")
        self.running = True

        # 创建事件循环
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        # 启动QUIC服务器(在新线程中运行事件循环)
        def run_event_loop():
            asyncio.set_event_loop(self.loop)
            self.loop.run_until_complete(self._run_quic_server())

        quic_thread = threading.Thread(target=run_event_loop, daemon=True)
        quic_thread.start()

        # 启动主循环
        self.main_thread = threading.Thread(target=self._main_loop)
        self.main_thread.start()

    def stop(self):
        """停止服务器"""
        if not self.running:
            logger.warning("服务器未运行")
            return

        logger.info("正在停止服务器...")
        self.running = False

        # 停止QUIC服务器
        if self.loop:
            # 等待异步stop完成
            future = asyncio.run_coroutine_threadsafe(self.quic_server.stop(), self.loop)
            try:
                future.result(timeout=5.0)
            except Exception as e:
                logger.error(f"等待QUIC服务器关闭超时或异常: {e}")

        # 等待主线程结束
        if self.main_thread and self.main_thread.is_alive():
            self.main_thread.join(timeout=5.0)

        logger.info("服务器已停止")


def parse_arguments():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description="弱网场景下视频流传输系统 - 服务端")

    parser.add_argument("--host", default="0.0.0.0", help="服务器监听地址")
    parser.add_argument("--port", type=int, default=4433, help="服务器监听端口")
    parser.add_argument("--fps", type=int, default=30, help="目标帧率")
    parser.add_argument("--bitrate", type=int, default=3000000, help="初始码率(bps)")
    parser.add_argument("--no-roi", action="store_true", help="禁用ROI编码")

    return parser.parse_args()


def main():
    """主函数"""
    # 解析命令行参数
    args = parse_arguments()

    # 创建服务器
    server = VideoStreamingServer(
        host=args.host,
        port=args.port,
        fps=args.fps,
        bitrate=args.bitrate,
        use_roi=not args.no_roi
    )

    # 注册信号处理
    def signal_handler(sig, frame):
        logger.info(f"接收到信号: {sig}")
        server.stop()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # 启动服务器
    try:
        server.start()

        # 保持主线程运行
        while server.running:
            time.sleep(1)

    except KeyboardInterrupt:
        logger.info("接收到用户中断")
    finally:
        server.stop()


if __name__ == "__main__":
    main()