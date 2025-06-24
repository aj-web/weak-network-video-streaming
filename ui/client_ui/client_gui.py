# ui/client_ui/client_gui.py

import sys
import time
import threading
import cv2
import numpy as np
import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk

# ui/client_ui/client_gui.py (续)

class ClientGUI:
    """客户端GUI界面"""
    
    def __init__(self, client):
        """
        初始化客户端GUI
        
        Args:
            client: VideoClient实例
        """
        self.client = client
        
        # 创建主窗口
        self.root = tk.Tk()
        self.root.title("Video Streaming Client")
        self.root.geometry("1000x700")
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
        
        # 连接/断开按钮
        self.connect_button = ttk.Button(control_frame, text="Connect", command=self.on_connect)
        self.connect_button.pack(side=tk.LEFT, padx=5)
        
        self.disconnect_button = ttk.Button(control_frame, text="Disconnect", command=self.on_disconnect)
        self.disconnect_button.pack(side=tk.LEFT, padx=5)
        
        # 连接状态标签
        self.status_label = ttk.Label(control_frame, text="Status: Disconnected")
        self.status_label.pack(side=tk.LEFT, padx=20)
        
        # FPS标签
        self.fps_label = ttk.Label(control_frame, text="FPS: 0")
        self.fps_label.pack(side=tk.LEFT, padx=20)
        
        # 创建选项卡控件
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # 视频选项卡
        self.video_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.video_frame, text="Video")
        
        # 视频画布
        self.video_canvas = tk.Canvas(self.video_frame, bg="black")
        self.video_canvas.pack(fill=tk.BOTH, expand=True)
        
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
        
        # 调试选项卡
        self.debug_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.debug_frame, text="Debug")
        
        # 网络模拟控制
        ttk.Label(self.debug_frame, text="Network Simulation").pack(pady=10)
        
        # 延迟控制
        delay_frame = ttk.Frame(self.debug_frame)
        delay_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Label(delay_frame, text="Delay (ms):").pack(side=tk.LEFT)
        self.delay_var = tk.StringVar(value="50")
        delay_values = ["50", "100", "150", "200", "300", "400"]
        self.delay_combo = ttk.Combobox(delay_frame, textvariable=self.delay_var, values=delay_values, width=10)
        self.delay_combo.pack(side=tk.LEFT, padx=5)
        
        # 丢包率控制
        loss_frame = ttk.Frame(self.debug_frame)
        loss_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Label(loss_frame, text="Packet Loss (%):").pack(side=tk.LEFT)
        self.loss_var = tk.StringVar(value="1")
        loss_values = ["0", "1", "2", "5", "10"]
        self.loss_combo = ttk.Combobox(loss_frame, textvariable=self.loss_var, values=loss_values, width=10)
        self.loss_combo.pack(side=tk.LEFT, padx=5)
        
        # 应用网络模拟按钮
        self.apply_button = ttk.Button(self.debug_frame, text="Apply Network Simulation", command=self.on_apply_network)
        self.apply_button.pack(pady=10)
        
        # 模拟状态标签
        self.sim_status_label = ttk.Label(self.debug_frame, text="Simulation: Off")
        self.sim_status_label.pack(pady=5)
        
        # 底部状态栏
        self.statusbar = ttk.Label(self.root, text="Ready", relief=tk.SUNKEN, anchor=tk.W)
        self.statusbar.pack(side=tk.BOTTOM, fill=tk.X)
    
    def on_connect(self):
        """连接到服务器"""
        if hasattr(self.client, 'start'):
            self.client.start()
            self.status_label.config(text="Status: Connected")
            self.statusbar.config(text=f"Connected to {self.client.server_host}:{self.client.server_port}")
    
    def on_disconnect(self):
        """断开连接"""
        if hasattr(self.client, 'stop'):
            self.client.stop()
            self.status_label.config(text="Status: Disconnected")
            self.statusbar.config(text="Disconnected")
    
    def on_apply_network(self):
        """应用网络模拟"""
        try:
            delay = int(self.delay_var.get())
            loss = float(self.loss_var.get())
            
            # 在实际实现中，我们会调用网络模拟工具
            # 这里仅显示模拟状态
            self.sim_status_label.config(text=f"Simulation: On (Delay: {delay}ms, Loss: {loss}%)")
            self.statusbar.config(text=f"Applied network simulation: Delay={delay}ms, Loss={loss}%")
            
            # TODO: 实现实际的网络模拟(使用clumsy或其他工具)
        except ValueError:
            self.statusbar.config(text="Error: Invalid network simulation parameters")
    
    def on_closing(self):
        """关闭窗口处理"""
        self.is_running = False
        if hasattr(self.client, 'stop'):
            self.client.stop()
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
            # 获取客户端统计信息
            stats = self.client.get_stats() if hasattr(self.client, 'get_stats') else {}
            
            # 更新FPS标签
            fps = stats.get("current_fps", 0)
            self.fps_label.config(text=f"FPS: {fps:.1f}")
            
            # 更新视频显示
            self._update_video()
            
            # 更新统计信息
            self._update_stats(stats)
            
            # 更新网络信息
            self._update_network(stats.get("network", {}))
        except Exception as e:
            self.statusbar.config(text=f"Error: {str(e)}")
    
    def _update_video(self):
        """更新视频显示"""
        # 从解码器获取最新帧
        if hasattr(self.client, 'decoder') and hasattr(self.client.decoder, 'get_frame'):
            frame = self.client.decoder.get_frame(block=False)
            
            if frame is not None:
                # 调整画布大小
                width, height = self.video_canvas.winfo_width(), self.video_canvas.winfo_height()
                
                if width > 1 and height > 1:
                    # 调整帧大小
                    frame = cv2.resize(frame, (width, height))
                    
                    # 转换为PIL图像
                    img = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    img = Image.fromarray(img)
                    img_tk = ImageTk.PhotoImage(image=img)
                    
                    # 显示图像
                    self.video_canvas.create_image(0, 0, anchor=tk.NW, image=img_tk)
                    self.video_canvas.image = img_tk  # 保持引用
    
    def _update_stats(self, stats):
        """更新统计信息"""
        # 清空文本框
        self.stats_text.delete(1.0, tk.END)
        
        # 添加统计信息
        self.stats_text.insert(tk.END, "Client Statistics:\n\n")
        
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
        for module in ["transport", "decoder", "renderer"]:
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


def start_client_gui(client):
    """
    启动客户端GUI
    
    Args:
        client: VideoClient实例
    """
    gui = ClientGUI(client)
    gui.run()