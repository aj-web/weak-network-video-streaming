# ui/server_ui/server_gui.py

import sys
import time
import threading
import cv2
import numpy as np
import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk

class ServerGUI:
    """服务器GUI界面"""
    
    def __init__(self, server):
        """
        初始化服务器GUI
        
        Args:
            server: VideoServer实例
        """
        self.server = server
        
        # 创建主窗口
        self.root = tk.Tk()
        self.root.title("Video Streaming Server")
        self.root.geometry("1200x800")
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # 创建界面组件
        self._create_widgets()
        
        # 更新标志
        self.is_running = True
        
        # 启动更新线程
        self.update_thread = threading.Thread(target=self._update_loop)
        self.update_thread.daemon = True
        self.update_thread.start()
    
    def _create_widgets(self):
        """创建界面组件"""
        # 创建顶部控制栏
        control_frame = ttk.Frame(self.root)
        control_frame.pack(fill=tk.X, padx=10, pady=5)
        
        # 启动/停止按钮
        self.start_button = ttk.Button(control_frame, text="Start", command=self.on_start)
        self.start_button.pack(side=tk.LEFT, padx=5)
        
        self.stop_button = ttk.Button(control_frame, text="Stop", command=self.on_stop)
        self.stop_button.pack(side=tk.LEFT, padx=5)
        
        # 服务器状态标签
        self.status_label = ttk.Label(control_frame, text="Server: Stopped")
        self.status_label.pack(side=tk.LEFT, padx=20)
        
        # 客户端计数标签
        self.client_label = ttk.Label(control_frame, text="Clients: 0")
        self.client_label.pack(side=tk.LEFT, padx=20)
        
        # FPS标签
        self.fps_label = ttk.Label(control_frame, text="FPS: 0")
        self.fps_label.pack(side=tk.LEFT, padx=20)
        
        # 创建选项卡控件
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # 预览选项卡
        self.preview_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.preview_frame, text="Preview")
        
        # 预览画布
        self.preview_canvas = tk.Canvas(self.preview_frame, bg="black")
        self.preview_canvas.pack(fill=tk.BOTH, expand=True)
        
        # ROI可视化选项卡
        self.roi_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.roi_frame, text="ROI Visualization")
        
        # ROI画布
        self.roi_canvas = tk.Canvas(self.roi_frame, bg="black")
        self.roi_canvas.pack(fill=tk.BOTH, expand=True)
        
        # 统计选项卡
        self.stats_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.stats_frame, text="Statistics")
        
        # 统计文本框
        self.stats_text = tk.Text(self.stats_frame, wrap=tk.WORD, bg="white")
        self.stats_text.pack(fill=tk.BOTH, expand=True)
        
        # 网络选项卡
        self.network_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.network_frame, text="Network")
        
        # 网络统计文本框
        self.network_text = tk.Text(self.network_frame, wrap=tk.WORD, bg="white")
        self.network_text.pack(fill=tk.BOTH, expand=True)
        
        # 底部状态栏
        self.statusbar = ttk.Label(self.root, text="Ready", relief=tk.SUNKEN, anchor=tk.W)
        self.statusbar.pack(side=tk.BOTTOM, fill=tk.X)
    
    def on_start(self):
        """启动服务器"""
        if hasattr(self.server, 'start'):
            self.server.start()
            self.status_label.config(text="Server: Running")
            self.statusbar.config(text=f"Server started on port {self.server.transport.port}")
    
    def on_stop(self):
        """停止服务器"""
        if hasattr(self.server, 'stop'):
            self.server.stop()
            self.status_label.config(text="Server: Stopped")
            self.statusbar.config(text="Server stopped")
    
    def on_closing(self):
        """关闭窗口处理"""
        self.is_running = False
        if hasattr(self.server, 'stop'):
            self.server.stop()
        self.root.destroy()
    
    def _update_loop(self):
        """更新线程主循环"""
        while self.is_running:
            try:
                # 更新界面
                self.root.after(100, self._update_ui)
                
                # 每秒更新一次
                time.sleep(0.1)
            except:
                break
    
    def _update_ui(self):
        """更新UI"""
        try:
            # 获取服务器统计信息
            stats = self.server.get_stats() if hasattr(self.server, 'get_stats') else {}
            
            # 更新FPS标签
            fps = stats.get("current_fps", 0)
            self.fps_label.config(text=f"FPS: {fps:.1f}")
            
            # 更新客户端计数
            client_count = self.server.transport.get_client_count() if hasattr(self.server.transport, 'get_client_count') else 0
            self.client_label.config(text=f"Clients: {client_count}")
            
            # 更新预览
            self._update_preview()
            
            # 更新ROI可视化
            self._update_roi_visualization()
            
            # 更新统计信息
            self._update_stats(stats)
            
            # 更新网络信息
            self._update_network(stats.get("network", {}))
        except Exception as e:
            self.statusbar.config(text=f"Error: {str(e)}")
    
    def _update_preview(self):
        """更新预览画面"""
        # 在实际实现中，我们会从服务器获取当前的视频帧
        # 这里我们创建一个简单的示例帧
        if hasattr(self.server, 'capturer') and hasattr(self.server.capturer, 'get_frame'):
            frame = self.server.capturer.get_frame(block=False)
            
            if frame is not None:
                # 调整画布大小
                width, height = self.preview_canvas.winfo_width(), self.preview_canvas.winfo_height()
                
                if width > 1 and height > 1:
                    # 调整帧大小
                    frame = cv2.resize(frame, (width, height))
                    
                    # 转换为PIL图像
                    img = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    img = Image.fromarray(img)
                    img_tk = ImageTk.PhotoImage(image=img)
                    
                    # 显示图像
                    self.preview_canvas.create_image(0, 0, anchor=tk.NW, image=img_tk)
                    self.preview_canvas.image = img_tk  # 保持引用
    
    def _update_roi_visualization(self):
        """更新ROI可视化"""
        if hasattr(self.server, 'get_roi_visualization'):
            roi_image = self.server.get_roi_visualization()
            
            if roi_image is not None:
                # 调整画布大小
                width, height = self.roi_canvas.winfo_width(), self.roi_canvas.winfo_height()
                
                if width > 1 and height > 1:
                    # 调整图像大小
                    roi_image = cv2.resize(roi_image, (width, height))
                    
                    # 转换为PIL图像
                    img = cv2.cvtColor(roi_image, cv2.COLOR_BGR2RGB)
                    img = Image.fromarray(img)
                    img_tk = ImageTk.PhotoImage(image=img)
                    
                    # 显示图像
                    self.roi_canvas.create_image(0, 0, anchor=tk.NW, image=img_tk)
                    self.roi_canvas.image = img_tk  # 保持引用
    
    def _update_stats(self, stats):
        """更新统计信息"""
        # 清空文本框
        self.stats_text.delete(1.0, tk.END)
        
        # 添加统计信息
        self.stats_text.insert(tk.END, "Server Statistics:\n\n")
        
        for key, value in stats.items():
            if isinstance(value, dict):
                continue
            
            if key == "start_time":
                # 格式化时间
                time_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(value))
                self.stats_text.insert(tk.END, f"{key}: {time_str}\n")
            elif key == "uptime":
                # 格式化运行时间
                minutes, seconds = divmod(int(value), 60)
                hours, minutes = divmod(minutes, 60)
                self.stats_text.insert(tk.END, f"{key}: {hours:02d}:{minutes:02d}:{seconds:02d}\n")
            else:
                # 其他统计
                if isinstance(value, float):
                    self.stats_text.insert(tk.END, f"{key}: {value:.2f}\n")
                else:
                    self.stats_text.insert(tk.END, f"{key}: {value}\n")
        
        # 添加模块统计
        for module in ["capturer", "encoder", "transport"]:
            if module in stats:
                self.stats_text.insert(tk.END, f"\n{module.capitalize()} Statistics:\n")
                
                for key, value in stats[module].items():
                    if isinstance(value, float):
                        self.stats_text.insert(tk.END, f"  {key}: {value:.2f}\n")
                    else:
                        self.stats_text.insert(tk.END, f"  {key}: {value}\n")
    
    def _update_network(self, network_stats):
        """更新网络信息"""
        # 清空文本框
        self.network_text.delete(1.0, tk.END)
        
        # 添加网络统计信息
        self.network_text.insert(tk.END, "Network Statistics:\n\n")
        
        for key, value in network_stats.items():
            if key == "rtt":
                self.network_text.insert(tk.END, f"RTT: {value:.2f} ms\n")
            elif key == "packet_loss":
                self.network_text.insert(tk.END, f"Packet Loss: {value*100:.2f}%\n")
            elif key == "bandwidth":
                self.network_text.insert(tk.END, f"Bandwidth: {value/1000000:.2f} Mbps\n")
            elif isinstance(value, float):
                self.network_text.insert(tk.END, f"{key}: {value:.2f}\n")
            else:
                self.network_text.insert(tk.END, f"{key}: {value}\n")
    
    def run(self):
        """运行GUI主循环"""
        self.root.mainloop()


def start_server_gui(server):
    """
    启动服务器GUI
    
    Args:
        server: VideoServer实例
    """
    gui = ServerGUI(server)
    gui.run()