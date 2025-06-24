# server/main.py

import time
import threading
import cv2
import argparse
import sys
import os

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from server.capture.screen_capturer import ScreenCapturer
from server.encoder.adaptive_encoder import AdaptiveEncoder
from server.encoder.roi_detector import ROIDetector
from server.network.transport_server import TransportServer
from common.config import Config
from ui.server_ui.server_gui import start_server_gui

# server/main.py

class VideoServer:
    """视频服务器主类"""
    
    def __init__(self, config=None):
        """
        初始化视频服务器
        
        Args:
            config: 配置对象
        """
        self.config = config if config else Config()
        
        # 默认视频参数
        self.width = self.config.VIDEO_WIDTH
        self.height = self.config.VIDEO_HEIGHT
        self.fps = self.config.TARGET_FPS
        
        # 初始化各模块
        self._init_modules()
        
        # 控制标志
        self.is_running = False
        self.main_thread = None
        
        # 性能统计
        self.stats = {
            "start_time": 0,
            "frames_captured": 0,
            "frames_encoded": 0,
            "frames_sent": 0,
            "avg_capture_time": 0,
            "avg_encode_time": 0,
            "avg_send_time": 0,
            "current_fps": 0
        }
        
        # 其他状态
        self.last_network_update_time = 0
        self.network_update_interval = 1.0  # 秒
    
    def _init_modules(self):
        """初始化各功能模块"""
        # 屏幕捕获器
        self.capturer = ScreenCapturer(
            width=self.width,
            height=self.height,
            fps=self.fps
        )
        
        # ROI检测器
        self.roi_detector = ROIDetector(
            width=self.width,
            height=self.height,
            grid_size=8
        )
        
        # 初始编码配置
        initial_profile = self.config.EncodingProfiles.BALANCED
        
        # 视频编码器
        self.encoder = AdaptiveEncoder(
            width=initial_profile["resolution"][0],
            height=initial_profile["resolution"][1],
            fps=initial_profile["fps"],
            initial_bitrate=initial_profile["bitrate"],
            codec=initial_profile["codec"],
            preset=initial_profile["preset"],
            gop=initial_profile["gop"]
        )
        
        # 设置ROI检测器
        self.encoder.set_roi_detector(self.roi_detector)
        
        # 网络传输服务器
        self.transport = TransportServer(
            port=self.config.SERVER_PORT
        )
    
    def start(self):
        """启动服务器"""
        if self.is_running:
            return
        
        self.is_running = True
        
        # 启动各模块
        self.capturer.start()
        self.encoder.start()
        self.transport.start()
        
        # 启动主线程
        self.main_thread = threading.Thread(target=self._main_loop)
        self.main_thread.daemon = True
        self.main_thread.start()
        
        # 记录启动时间
        self.stats["start_time"] = time.time()
        
        print("Video server started")
    
    def stop(self):
        """停止服务器"""
        self.is_running = False
        
        if self.main_thread:
            self.main_thread.join(timeout=1.0)
            self.main_thread = None
        
        # 停止各模块
        self.capturer.stop()
        self.encoder.stop()
        self.transport.stop()
        
        # 清理ROI检测器
        if hasattr(self.roi_detector, 'cleanup'):
            self.roi_detector.cleanup()
        
        print("Video server stopped")
    
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
            # 捕获帧
            capture_start = time.time()
            frame = self.capturer.get_frame(block=True, timeout=0.1)  # 增加超时时间
            capture_time = time.time() - capture_start
            
            if frame is None:
                consecutive_none_frames += 1
                # 只在连续多次获取不到帧时才打印警告
                if consecutive_none_frames % 100 == 1:  # 每100次打印一次
                    print(f"Warning: Captured frame is None (连续{consecutive_none_frames}次)")
                time.sleep(0.01)  # 短暂等待
                continue
            
            # 重置None帧计数
            consecutive_none_frames = 0
            
            # 编码帧
            encode_start = time.time()
            self.encoder.encode_frame(frame, block=True, timeout=0.1)
            encode_time = time.time() - encode_start
            
            # 获取编码后的数据包
            packet = self.encoder.get_packet(block=False)
            
            if packet:
                # 发送帧
                send_start = time.time()
                self.transport.send_video_frame(
                    packet["data"], 
                    packet["frame_index"], 
                    packet["is_keyframe"],
                    packet["width"],
                    packet["height"],
                    packet.get("encoding_params", None)
                )
                send_time = time.time() - send_start
                
                # 更新统计信息
                self.stats["frames_sent"] += 1
                self.stats["avg_send_time"] = (self.stats["avg_send_time"] * (self.stats["frames_sent"] - 1) + send_time) / self.stats["frames_sent"]
            
            # 更新统计信息
            self.stats["frames_captured"] += 1
            self.stats["frames_encoded"] += 1
            self.stats["avg_capture_time"] = (self.stats["avg_capture_time"] * (self.stats["frames_captured"] - 1) + capture_time) / self.stats["frames_captured"]
            self.stats["avg_encode_time"] = (self.stats["avg_encode_time"] * (self.stats["frames_encoded"] - 1) + encode_time) / self.stats["frames_encoded"]
            
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
                print(f"[Server] FPS: {self.stats['current_fps']:.1f}, AvgCapture: {self.stats['avg_capture_time']*1000:.1f}ms, AvgEncode: {self.stats['avg_encode_time']*1000:.1f}ms, AvgSend: {self.stats['avg_send_time']*1000:.1f}ms, Sent: {self.stats['frames_sent']}")
                last_log_time = current_time
            
            # 定期更新网络反馈
            if time.time() - self.last_network_update_time >= self.network_update_interval:
                network_stats = self.transport.get_network_stats()
                self.encoder.update_network_feedback(network_stats)
                self.last_network_update_time = time.time()
    
    def get_stats(self):
        """获取服务器统计信息"""
        stats = self.stats.copy()
        
        # 添加各模块的统计信息
        if hasattr(self.capturer, 'stats'):
            stats["capturer"] = self.capturer.stats.copy()
        
        if hasattr(self.encoder, 'stats'):
            stats["encoder"] = self.encoder.stats.copy()
        
        if hasattr(self.transport, 'stats'):
            stats["transport"] = self.transport.stats.copy()
            
        # 添加网络统计
        stats["network"] = self.transport.get_network_stats()
        
        # 计算运行时间
        stats["uptime"] = time.time() - self.stats["start_time"]
        
        return stats
    
    def get_roi_visualization(self):
        """获取ROI可视化图像"""
        if hasattr(self.roi_detector, 'get_roi_visualization'):
            return self.roi_detector.get_roi_visualization()
        return None


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="Video Streaming Server for Weak Network")
    parser.add_argument("--port", type=int, default=Config.SERVER_PORT, help="Server port")
    parser.add_argument("--width", type=int, default=Config.VIDEO_WIDTH, help="Video width")
    parser.add_argument("--height", type=int, default=Config.VIDEO_HEIGHT, help="Video height")
    parser.add_argument("--fps", type=int, default=Config.TARGET_FPS, help="Target FPS")
    parser.add_argument("--nogui", action="store_true", help="Run without GUI")
    args = parser.parse_args()
    
    # 创建配置
    config = Config()
    config.SERVER_PORT = args.port
    config.VIDEO_WIDTH = args.width
    config.VIDEO_HEIGHT = args.height
    config.TARGET_FPS = args.fps
    
    # 创建服务器
    server = VideoServer(config)
    
    if args.nogui:
        try:
            # 无GUI模式
            server.start()
            print(f"Server running on port {args.port}. Press Ctrl+C to stop.")
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("Stopping server...")
            server.stop()
    else:
        # 启动GUI
        start_server_gui(server)


if __name__ == "__main__":
    main()