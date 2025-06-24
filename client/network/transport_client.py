# client/network/transport_client.py

import socket
import threading
import time
import queue
import random
from common.network_utils.protocol import *
from common.network_utils.monitoring import NetworkMonitor

class TransportClient:
    """视频传输客户端"""
    
    def __init__(self, server_host, server_port=8000):
        """
        初始化传输客户端
        
        Args:
            server_host: 服务器主机名或IP
            server_port: 服务器端口
        """
        self.server_host = server_host
        self.server_port = server_port
        self.server_addr = (server_host, server_port)

        try:
            # 创建UDP套接字
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.socket.bind(('0.0.0.0', 0))  # 绑定任意可用端口
        except Exception as e:
            print(f"Error creating socket: {e}")
            self.socket = None
        
        # 数据队列
        self.send_queue = queue.Queue(maxsize=100)
        self.receive_queue = queue.Queue(maxsize=1000)
        
        # 视频帧队列
        self.frame_queue = queue.Queue(maxsize=30)
        
        # 控制标志
        self.is_running = False
        self.is_connected = False
        
        # 线程
        self.receive_thread = None
        self.send_thread = None
        self.process_thread = None
        
        # 网络监控
        self.network_monitor = NetworkMonitor()
        
        # 序列号
        self.next_seq_num = 0
        
        # 帧重组缓冲区
        self.frame_fragments = {}  # frame_index -> [fragment1, fragment2, ...]
        
        # 接收到的帧计数
        self.received_frames = 0
        
        # 丢失的序列号跟踪
        self.received_seq_nums = set()
        self.expected_seq_num = 0
        self.missing_seq_nums = set()
        
        # 最后发送NACK的时间
        self.last_nack_time = 0
        self.nack_interval = 0.1  # 秒
        
        # 心跳控制
        self.last_heartbeat_time = 0
        self.heartbeat_interval = 1.0  # 秒
        
        # 统计信息
        self.stats = {
            "sent_packets": 0,
            "sent_bytes": 0,
            "received_packets": 0,
            "received_bytes": 0,
            "complete_frames": 0,
            "incomplete_frames": 0,
            "dropped_frames": 0,
            "network": {}
        }
    
    def connect(self):
        """连接到服务器"""
        # 如果套接字为None，尝试重新创建
        if self.socket is None:
            try:
                self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                if self.socket is None:
                    print("Failed to create socket")
                self.socket.bind(('0.0.0.0', 0))  # 绑定任意可用端口
            except Exception as e:
                print(f"Error recreating socket: {e}")
                return False

        # 发送初始心跳包建立连接
        heartbeat = HeartbeatPacket(
            seq_num=self.next_seq_num,
            timestamp=time.time(),
            client_stats={}
        )
        self.next_seq_num += 1
        
        # 序列化并发送
        packet_data = heartbeat.serialize()
        self.socket.sendto(packet_data, self.server_addr)
        
        # 等待心跳响应
        try:
            self.socket.settimeout(5.0)
            data, addr = self.socket.recvfrom(2048)
            packet = Packet.deserialize(data)
            
            if packet and packet.packet_type == PACKET_TYPE_HEARTBEAT:
                self.is_connected = True
                print(f"Connected to server at {self.server_host}:{self.server_port}")
                return True
        except:
            pass
        
        print(f"Failed to connect to server at {self.server_host}:{self.server_port}")
        return False
    
    def start(self):
        """启动客户端"""
        if self.is_running:
            return
        
        # 连接到服务器
        if not self.is_connected and not self.connect():
            return
        
        self.is_running = True
        
        # 启动接收线程
        self.receive_thread = threading.Thread(target=self._receive_loop)
        self.receive_thread.daemon = True
        self.receive_thread.start()
        
        # 启动发送线程
        self.send_thread = threading.Thread(target=self._send_loop)
        self.send_thread.daemon = True
        self.send_thread.start()
        
        # 启动处理线程
        self.process_thread = threading.Thread(target=self._process_loop)
        self.process_thread.daemon = True
        self.process_thread.start()
        
        print("Transport client started")
    
    def stop(self):
        """停止客户端"""
        self.is_running = False
        
        if self.receive_thread:
            self.receive_thread.join(timeout=1.0)
            self.receive_thread = None
        
        if self.send_thread:
            self.send_thread.join(timeout=1.0)
            self.send_thread = None
        
        if self.process_thread:
            self.process_thread.join(timeout=1.0)
            self.process_thread = None
        
        if self.socket:
            self.socket.close()
            self.socket = None
        
        self.is_connected = False
        print("Transport client stopped")
    
    def get_frame(self, block=True, timeout=None):
        """
        获取一个完整的视频帧
        
        Args:
            block: 是否阻塞等待
            timeout: 超时时间(秒)
            
        Returns:
            帧数据字典，或超时/队列为空时返回None
        """
        try:
            return self.frame_queue.get(block=block, timeout=timeout)
        except:
            return None
    
    def _receive_loop(self):
        """接收线程主循环"""
        while self.is_running:
            try:
                # 设置超时以便定期检查is_running标志
                self.socket.settimeout(0.1)
                
                # 接收数据
                data, addr = self.socket.recvfrom(4096)
                
                # 验证发送方是服务器（只检查端口号，不检查IP地址）
                if addr[1] != self.server_port:
                    print(f"收到来自错误端口的数据: {addr[1]} != {self.server_port}")
                    continue
                
                # 解析数据包
                packet = Packet.deserialize(data)
                
                if packet:
                    # 记录接收统计
                    self.stats["received_packets"] += 1
                    self.stats["received_bytes"] += len(data)
                    
                    # 记录接收到的序列号
                    self.received_seq_nums.add(packet.seq_num)
                    
                    # 检测丢失的包
                    if self.expected_seq_num < packet.seq_num:
                        for seq in range(self.expected_seq_num, packet.seq_num):
                            if seq not in self.received_seq_nums:
                                self.missing_seq_nums.add(seq)
                    
                    # 更新下一个期望的序列号
                    self.expected_seq_num = max(self.expected_seq_num, packet.seq_num + 1)
                    
                    # 将包放入接收队列
                    try:
                        self.receive_queue.put(packet, block=False)
                    except:
                        pass
                    
                    # 记录到网络监控
                    self.network_monitor.packet_received(packet)
                else:
                    print(f"无法解析数据包: {len(data)} 字节")
            except socket.timeout:
                continue
            except Exception as e:
                print(f"Error in receive loop: {e}")
                time.sleep(0.01)
    
    def _send_loop(self):
        """发送线程主循环"""
        while self.is_running:
            # 处理发送队列
            try:
                # 从队列获取要发送的数据包
                packet = self.send_queue.get(block=False)
                
                # 序列化数据包
                packet_data = packet.serialize()
                
                # 记录发送统计
                self.stats["sent_packets"] += 1
                self.stats["sent_bytes"] += len(packet_data)
                
                # 记录到网络监控
                self.network_monitor.packet_sent(packet)
                
                # 发送到服务器
                try:
                    self.socket.sendto(packet_data, self.server_addr)
                except:
                    pass
            except queue.Empty:
                pass
            
            # 定期发送NACK(请求重传丢失的包)
            now = time.time()
            if self.missing_seq_nums and now - self.last_nack_time >= self.nack_interval:
                self._send_nack()
                self.last_nack_time = now
            
            # 定期发送心跳
            if now - self.last_heartbeat_time >= self.heartbeat_interval:
                self._send_heartbeat()
                self.last_heartbeat_time = now
            
            # 小睡一下，避免CPU占用过高
            time.sleep(0.001)
    
    def _process_loop(self):
        """处理线程主循环，处理接收到的数据包"""
        while self.is_running:
            try:
                # 从接收队列获取数据包
                packet = self.receive_queue.get(block=True, timeout=0.1)
            except:
                continue
            
            # 处理不同类型的包
            if packet.packet_type == PACKET_TYPE_VIDEO:
                self._handle_video_packet(packet)
            elif packet.packet_type == PACKET_TYPE_FEC:
                self._handle_fec_packet(packet)
            elif packet.packet_type == PACKET_TYPE_HEARTBEAT:
                self._handle_heartbeat_packet(packet)
    
    def _handle_video_packet(self, packet):
        """
        处理视频数据包
        
        Args:
            packet: 视频数据包
        """
        if isinstance(packet, VideoPacket):
            # 获取帧索引
            frame_index = packet.frame_index
            
            # 将分片添加到帧重组缓冲区
            if frame_index not in self.frame_fragments:
                self.frame_fragments[frame_index] = []
            
            self.frame_fragments[frame_index].append(packet)
            
            # 检查帧是否完整
            if packet.is_last_fragment():
                fragments = self.frame_fragments.get(frame_index, [])
                
                # 尝试重组帧
                frame_data = reassemble_video_frame(fragments)
                
                if frame_data:
                    # 帧完整，放入帧队列
                    try:
                        self.frame_queue.put(frame_data, block=False)
                        self.stats["complete_frames"] += 1
                        self.received_frames += 1
                    except:
                        self.stats["dropped_frames"] += 1
                else:
                    # 帧不完整
                    self.stats["incomplete_frames"] += 1
                
                # 移除已处理的帧
                self.frame_fragments.pop(frame_index, None)
                
                # 清理过时的帧(保留最近30个帧的缓冲)
                self._cleanup_old_fragments(30)
    
    def _handle_fec_packet(self, packet):
        """
        处理FEC数据包
        
        Args:
            packet: FEC数据包
        """
        if isinstance(packet, FECPacket):
            # TODO: 实现FEC恢复逻辑
            # 在实际实现中，我们需要使用FEC数据恢复丢失的包
            pass
    
    def _handle_heartbeat_packet(self, packet):
        """
        处理心跳包
        
        Args:
            packet: 心跳包
        """
        if isinstance(packet, HeartbeatPacket):
            # 提取服务器统计信息
            server_stats = packet.client_stats
            
            # 更新网络统计
            if server_stats:
                self.stats["network"].update(server_stats)
    
    def _send_nack(self):
        """发送NACK请求重传丢失的包"""
        if not self.missing_seq_nums:
            return
        
        # 限制NACK包大小(最多请求100个序列号)
        missing_seqs = list(self.missing_seq_nums)[:100]
        
        # 创建NACK包
        nack = ControlPacket(
            seq_num=self.next_seq_num,
            ctrl_type=ControlPacket.CTRL_TYPE_NACK,
            ctrl_data={"missing_seqs": missing_seqs}
        )
        self.next_seq_num += 1
        
        # 放入发送队列
        try:
            self.send_queue.put(nack, block=False)
            
            # 从丢失集合中移除已请求的序列号
            for seq in missing_seqs:
                self.missing_seq_nums.remove(seq)
        except:
            pass
    
    def _send_heartbeat(self):
        """发送心跳包"""
        # 获取当前网络统计
        network_stats = self.network_monitor.get_current_stats()
        
        # 添加客户端统计
        client_stats = {
            "rtt": network_stats.get("rtt", 0),
            "packet_loss": network_stats.get("packet_loss", 0),
            "received_frames": self.received_frames,
            "missing_packets": len(self.missing_seq_nums)
        }
        
        # 创建心跳包
        heartbeat = HeartbeatPacket(
            seq_num=self.next_seq_num,
            timestamp=time.time(),
            client_stats=client_stats
        )
        self.next_seq_num += 1
        
        # 放入发送队列
        try:
            self.send_queue.put(heartbeat, block=False)
        except:
            pass
    
    def _cleanup_old_fragments(self, keep_count):
        """
        清理旧的帧分片
        
        Args:
            keep_count: 保留的最近帧数量
        """
        if len(self.frame_fragments) <= keep_count:
            return
        
        # 找出所有帧索引并排序
        frame_indices = sorted(self.frame_fragments.keys())
        
        # 移除旧帧
        for idx in frame_indices[:-keep_count]:
            self.frame_fragments.pop(idx, None)
    
    def get_network_stats(self):
        """获取网络统计信息"""
        return self.network_monitor.get_current_stats()