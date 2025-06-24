# common/network_utils/monitoring.py

import time
import threading
import collections
import numpy as np
from queue import Queue

class NetworkMonitor:
    """网络状态监控类"""
    
    def __init__(self, window_size=100):
        """
        初始化网络监控器
        
        Args:
            window_size: 滑动窗口大小，用于计算统计值
        """
        self.window_size = window_size
        
        # 滑动窗口，用于记录历史数据
        self.rtt_window = collections.deque(maxlen=window_size)
        self.loss_window = collections.deque(maxlen=window_size)
        self.bandwidth_window = collections.deque(maxlen=window_size)
        
        # 当前统计值
        self.current_stats = {
            "rtt": 0,             # ms
            "rtt_variance": 0,    # ms
            "packet_loss": 0,     # 0-1
            "bandwidth": 0,       # bps
            "bandwidth_variance": 0,  # bps
            "last_update_time": 0
        }
        
        # 数据包追踪，用于计算RTT和丢包率
        self.packet_tracking = {}
        self.packet_sent_count = 0
        self.packet_received_count = 0
        
        # 带宽测量
        self.bytes_received = 0
        self.last_bytes_time = time.time()
        
        # 传输队列大小监控
        self.queue_size_history = collections.deque(maxlen=window_size)
        
        # 历史统计
        self.history = []
        
        # 锁，保护共享数据
        self.lock = threading.Lock()
        
        # 网络分类器
        self.network_classifier = NetworkClassifier()
        
        # 网络预测器(简单版)
        self.predictor = SimpleNetworkPredictor(window_size=10)
    
    def packet_sent(self, packet):
        """
        记录数据包发送
        
        Args:
            packet: 发送的数据包
        """
        with self.lock:
            # 记录发送时间
            self.packet_tracking[packet.seq_num] = {
                "send_time": time.time(),
                "size": len(packet.serialize())
            }
            self.packet_sent_count += 1
    
    def packet_received(self, packet):
        """
        记录数据包接收
        
        Args:
            packet: 接收的数据包
        """
        now = time.time()
        
        with self.lock:
            # 查找对应的发送记录
            sent_info = self.packet_tracking.pop(packet.seq_num, None)
            
            if sent_info:
                # 计算RTT
                rtt = (now - sent_info["send_time"]) * 1000  # ms
                self.rtt_window.append(rtt)
                
                # 更新带宽测量
                self.bytes_received += sent_info["size"]
                
                # 更新数据包计数
                self.packet_received_count += 1
            
            # 更新当前统计
            self._update_stats()
    
    def _update_stats(self):
        """更新当前网络统计"""
        now = time.time()
        
        # 计算RTT统计
        if self.rtt_window:
            self.current_stats["rtt"] = np.mean(self.rtt_window)
            self.current_stats["rtt_variance"] = np.std(self.rtt_window)
        
        # 计算丢包率
        if self.packet_sent_count > 0:
            loss_rate = 1.0 - (self.packet_received_count / self.packet_sent_count)
            self.loss_window.append(loss_rate)
            self.current_stats["packet_loss"] = np.mean(self.loss_window)
        
        # 计算带宽
        time_diff = now - self.last_bytes_time
        if time_diff >= 1.0:  # 至少1秒
            bandwidth = (self.bytes_received * 8) / time_diff  # bps
            self.bandwidth_window.append(bandwidth)
            
            if self.bandwidth_window:
                self.current_stats["bandwidth"] = np.mean(self.bandwidth_window)
                self.current_stats["bandwidth_variance"] = np.std(self.bandwidth_window)
            
            # 重置带宽测量
            self.bytes_received = 0
            self.last_bytes_time = now
        
        # 更新最后更新时间
        self.current_stats["last_update_time"] = now
        
        # 定期保存历史数据
        if len(self.history) == 0 or now - self.history[-1]["time"] >= 1.0:
            history_entry = self.current_stats.copy()
            history_entry["time"] = now
            self.history.append(history_entry)
            
            # 限制历史记录大小
            if len(self.history) > 3600:  # 保留1小时的数据(假设1秒1个)
                self.history.pop(0)
        
        # 更新网络类型
        self.network_classifier.update(self.current_stats)
        
        # 更新预测
        self.predictor.update(self.current_stats)
    
    def get_current_stats(self):
        """获取当前网络统计"""
        with self.lock:
            return self.current_stats.copy()
    
    def get_network_type(self):
        """获取当前网络类型"""
        return self.network_classifier.get_network_type()
    
    def predict_network_stats(self, time_ahead_ms=500):
        """
        预测未来网络状态
        
        Args:
            time_ahead_ms: 预测多久之后的网络状态(毫秒)
            
        Returns:
            预测的网络统计
        """
        return self.predictor.predict(time_ahead_ms)
    
    def update_queue_size(self, queue_size):
        """
        更新传输队列大小
        
        Args:
            queue_size: 当前队列大小
        """
        with self.lock:
            self.queue_size_history.append(queue_size)
    
    def get_congestion_level(self):
        """
        获取拥塞级别(0-1)
        
        Returns:
            拥塞级别，0表示无拥塞，1表示严重拥塞
        """
        with self.lock:
            # 基于RTT和队列大小估计拥塞级别
            if not self.rtt_window or not self.queue_size_history:
                return 0.0
                
            # 归一化RTT
            rtt_min = min(self.rtt_window)
            rtt_max = max(self.rtt_window)
            if rtt_max == rtt_min:
                rtt_norm = 0.0
            else:
                rtt_norm = (self.current_stats["rtt"] - rtt_min) / (rtt_max - rtt_min)
            
            # 归一化队列大小
            queue_max = max(self.queue_size_history)
            if queue_max == 0:
                queue_norm = 0.0
            else:
                queue_norm = sum(self.queue_size_history) / (len(self.queue_size_history) * queue_max)
            
            # 综合考虑RTT和队列大小
            congestion = 0.7 * rtt_norm + 0.3 * queue_norm
            
            return min(1.0, max(0.0, congestion))


class NetworkClassifier:
    """网络类型分类器"""
    
    # 网络类型定义
    NETWORK_TYPE_EXCELLENT = 0
    NETWORK_TYPE_GOOD = 1
    NETWORK_TYPE_FAIR = 2
    NETWORK_TYPE_POOR = 3
    NETWORK_TYPE_VERY_POOR = 4
    
    # 网络类型阈值
    NETWORK_THRESHOLDS = {
        NETWORK_TYPE_EXCELLENT: {
            "rtt": 50,            # ms
            "packet_loss": 0.01,  # 1%
            "bandwidth": 10000000  # 10 Mbps
        },
        NETWORK_TYPE_GOOD: {
            "rtt": 100,
            "packet_loss": 0.02,
            "bandwidth": 5000000  # 5 Mbps
        },
        NETWORK_TYPE_FAIR: {
            "rtt": 200,
            "packet_loss": 0.05,
            "bandwidth": 2000000  # 2 Mbps
        },
        NETWORK_TYPE_POOR: {
            "rtt": 300,
            "packet_loss": 0.10,
            "bandwidth": 1000000  # 1 Mbps
        }
        # 超过POOR阈值则为VERY_POOR
    }
    
    def __init__(self):
        """初始化网络分类器"""
        self.current_type = self.NETWORK_TYPE_GOOD  # 默认为良好
        self.type_stability = 0  # 类型稳定性计数器
        self.TYPE_SWITCH_THRESHOLD = 3  # 需要连续多少次才切换类型
    
    def update(self, stats):
        """
        更新网络类型
        
        Args:
            stats: 当前网络统计
        """
        # 确定当前应该的类型
        detected_type = self._classify(stats)
        
        # 类型相同，增加稳定性计数
        if detected_type == self.current_type:
            self.type_stability = min(self.type_stability + 1, self.TYPE_SWITCH_THRESHOLD)
        else:
            # 类型不同，减少稳定性计数
            self.type_stability -= 1
            
            # 如果稳定性降到0，切换类型
            if self.type_stability <= 0:
                self.current_type = detected_type
                self.type_stability = 0
    
    def _classify(self, stats):
        """
        根据网络统计分类网络类型
        
        Args:
            stats: 网络统计
            
        Returns:
            网络类型
        """
        # 从最好到最差逐个检查
        for network_type in range(self.NETWORK_TYPE_EXCELLENT, self.NETWORK_TYPE_VERY_POOR):
            thresholds = self.NETWORK_THRESHOLDS.get(network_type)
            
            # 检查是否满足所有阈值
            if (stats["rtt"] <= thresholds["rtt"] and
                stats["packet_loss"] <= thresholds["packet_loss"] and
                stats["bandwidth"] >= thresholds["bandwidth"]):
                return network_type
        
        # 默认为最差
        return self.NETWORK_TYPE_VERY_POOR
    
    def get_network_type(self):
        """获取当前网络类型"""
        return self.current_type
    
    def get_network_type_name(self):
        """获取当前网络类型名称"""
        names = {
            self.NETWORK_TYPE_EXCELLENT: "Excellent",
            self.NETWORK_TYPE_GOOD: "Good",
            self.NETWORK_TYPE_FAIR: "Fair",
            self.NETWORK_TYPE_POOR: "Poor",
            self.NETWORK_TYPE_VERY_POOR: "Very Poor"
        }
        return names.get(self.current_type, "Unknown")


class SimpleNetworkPredictor:
    """简单网络预测器"""
    
    def __init__(self, window_size=10):
        """
        初始化网络预测器
        
        Args:
            window_size: 滑动窗口大小
        """
        self.window_size = window_size
        self.stats_history = collections.deque(maxlen=window_size)
        self.last_update_time = 0
    
    def update(self, stats):
        """
        更新网络统计历史
        
        Args:
            stats: 当前网络统计
        """
        now = time.time()
        
        # 只有在一定时间间隔后才更新
        if now - self.last_update_time >= 0.1:  # 100ms
            self.stats_history.append({
                "time": now,
                "rtt": stats["rtt"],
                "packet_loss": stats["packet_loss"],
                "bandwidth": stats["bandwidth"]
            })
            self.last_update_time = now
    
    def predict(self, time_ahead_ms):
        """
        预测未来网络状态
        
        Args:
            time_ahead_ms: 预测多久之后的网络状态(毫秒)
            
        Returns:
            预测的网络统计
        """
        if len(self.stats_history) < 2:
            # 历史数据不足，返回最新值
            if self.stats_history:
                return self.stats_history[-1].copy()
            else:
                return {
                    "rtt": 100,
                    "packet_loss": 0.01,
                    "bandwidth": 5000000
                }
        
        # 简单线性预测
        # 计算最近的趋势
        latest = self.stats_history[-1]
        prev = self.stats_history[0]
        
        time_diff = latest["time"] - prev["time"]
        if time_diff <= 0:
            return latest.copy()
        
        # 计算变化率
        rtt_rate = (latest["rtt"] - prev["rtt"]) / time_diff
        loss_rate = (latest["packet_loss"] - prev["packet_loss"]) / time_diff
        bw_rate = (latest["bandwidth"] - prev["bandwidth"]) / time_diff
        
        # 预测未来值
        time_ahead = time_ahead_ms / 1000.0  # 转换为秒
        
        prediction = {
            "time": latest["time"] + time_ahead,
            "rtt": max(0, latest["rtt"] + rtt_rate * time_ahead),
            "packet_loss": max(0, min(1.0, latest["packet_loss"] + loss_rate * time_ahead)),
            "bandwidth": max(0, latest["bandwidth"] + bw_rate * time_ahead)
        }
        
        return prediction