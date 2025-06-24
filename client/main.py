# client/main.py

import time
import threading
import cv2
import argparse
import sys
import os

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from client.decoder.video_decoder import VideoDecoder
from client.network.transport_client import TransportClient
from client.renderer.frame_renderer import FrameRenderer
from common.config import Config
from ui.client_ui.client_gui import start_client_gui




# client/main.py (续)

class VideoClient:
    """视频客户端主类"""
    
    def __init__(self, server_host, server_port=8000, config=None):
        """
        初始化视频客户端
        
        Args:
            server_host: 服务器主机名或IP
            server_port: 服务器端口
            config: 配置对象
        """
        self.server_host = server_host
        self.server_port = server_port
        self.config = config if config else Config()
        
        # 初始化各模块
        self._init_modules()
        
        # 控制标志
        self.is_running = False
        self.main_thread = None
        
        # 性能统计
        self.stats = {
            "start_time": 0,
            "frames_received": 0,
            "frames_decoded": 0,
            "frames_displayed": 0,
            "avg_receive_time": 0,
            "avg_decode_time": 0,
            "avg_display_time": 0,
            "current_fps": 0
        }
        
        # 帧间延迟
        self.frame_delay = 1.0 / 30  # 默认30fps
    
    def _init_modules(self):
        """初始化各功能模块"""
        # 网络传输客户端
        self.transport = TransportClient(
            server_host=self.server_host,
            server_port=self.server_port
        )
        
        # 视频解码器
        self.decoder = VideoDecoder()
        
        # 帧渲染器
        self.renderer = FrameRenderer()
    
    def start(self):
        """启动客户端"""
        if self.is_running:
            return
        
        self.is_running = True
        
        # 启动各模块
        self.transport.start()
        self.decoder.start()
        self.renderer.start()
        
        # 启动主线程
        self.main_thread = threading.Thread(target=self._main_loop)
        self.main_thread.daemon = True
        self.main_thread.start()
        
        # 记录启动时间
        self.stats["start_time"] = time.time()
        
        print("Video client started")
    
    def stop(self):
        """停止客户端"""
        self.is_running = False
        
        if self.main_thread:
            self.main_thread.join(timeout=1.0)
            self.main_thread = None
        
        # 停止各模块
        self.renderer.stop()
        self.decoder.stop()
        self.transport.stop()
        
        print("Video client stopped")
    
    def _main_loop(self):
        """主循环"""
        # 等待各模块完全启动
        time.sleep(0.5)
        
        last_time = time.time()
        frame_count = 0
        log_interval = 10.0
        last_log_time = time.time()
        consecutive_none_frames = 0  # 连续None帧计数
        
        while self.is_running:
            # 接收网络帧
            receive_start = time.time()
            network_frame = self.transport.get_frame(block=True, timeout=0.1)  # 增加超时时间
            receive_time = time.time() - receive_start
            
            if network_frame:
                # 重置None帧计数
                consecutive_none_frames = 0
                
                # 解码帧
                decode_start = time.time()
                self.decoder.decode_frame(network_frame, block=True)
                decode_time = time.time() - decode_start
                
                # 获取解码后的帧
                decoded_frame = self.decoder.get_frame(block=False)
                
                if decoded_frame is not None:
                    # 渲染帧
                    display_start = time.time()
                    self.renderer.render_frame(decoded_frame)
                    display_time = time.time() - display_start
                    
                    # 更新统计信息
                    self.stats["frames_displayed"] += 1
                    self.stats["avg_display_time"] = (self.stats["avg_display_time"] * (self.stats["frames_displayed"] - 1) + display_time) / self.stats["frames_displayed"]
                
                # 更新统计信息
                self.stats["frames_received"] += 1
                self.stats["frames_decoded"] += 1
                self.stats["avg_receive_time"] = (self.stats["avg_receive_time"] * (self.stats["frames_received"] - 1) + receive_time) / self.stats["frames_received"]
                self.stats["avg_decode_time"] = (self.stats["avg_decode_time"] * (self.stats["frames_decoded"] - 1) + decode_time) / self.stats["frames_decoded"]
                
                # 计算当前FPS
                frame_count += 1
                current_time = time.time()
                time_diff = current_time - last_time
                
                if time_diff >= 1.0:
                    self.stats["current_fps"] = frame_count / time_diff
                    frame_count = 0
                    last_time = current_time
                
                # 每10秒打印一次统计信息
                if current_time - last_log_time >= log_interval:
                    print(f"[Client] FPS: {self.stats['current_fps']:.1f}, AvgRecv: {self.stats['avg_receive_time']*1000:.1f}ms, AvgDecode: {self.stats['avg_decode_time']*1000:.1f}ms, AvgDisp: {self.stats['avg_display_time']*1000:.1f}ms, Displayed: {self.stats['frames_displayed']}")
                    last_log_time = current_time
            else:
                consecutive_none_frames += 1
                # 只在连续多次获取不到帧时才打印警告
                if consecutive_none_frames % 100 == 1:  # 每100次打印一次
                    print(f"Warning: No network frame received (连续{consecutive_none_frames}次)")
                # 如果没有收到新帧，小睡一下避免CPU占用过高
                time.sleep(0.01)
    
    def get_stats(self):
        """获取客户端统计信息"""
        stats = self.stats.copy()
        
        # 添加各模块的统计信息
        if hasattr(self.transport, 'stats'):
            stats["transport"] = self.transport.stats.copy()
        
        if hasattr(self.decoder, 'stats'):
            stats["decoder"] = self.decoder.stats.copy()
        
        if hasattr(self.renderer, 'stats'):
            stats["renderer"] = self.renderer.stats.copy()
            
        # 添加网络统计
        stats["network"] = self.transport.get_network_stats()
        
        # 计算运行时间
        stats["uptime"] = time.time() - self.stats["start_time"]
        
        return stats


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="Video Streaming Client for Weak Network")
    parser.add_argument("server", type=str, help="Server host or IP")
    parser.add_argument("--port", type=int, default=Config.SERVER_PORT, help="Server port")
    parser.add_argument("--nogui", action="store_true", help="Run without GUI")
    args = parser.parse_args()
    
    # 创建客户端
    client = VideoClient(args.server, args.port)
    
    if args.nogui:
        try:
            # 无GUI模式
            client.start()
            print(f"Client connected to {args.server}:{args.port}. Press Ctrl+C to stop.")
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("Stopping client...")
            client.stop()
    else:
        # 启动GUI
        start_client_gui(client)


if __name__ == "__main__":
    main()