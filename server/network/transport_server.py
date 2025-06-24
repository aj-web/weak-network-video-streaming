# server/network/transport_server.py

import socket
import threading
import time
import random
import queue
from common.network_utils.protocol import *
from common.network_utils.monitoring import NetworkMonitor

class TransportServer:
    """视频传输服务器"""
    
    def __init__(self, port=8000, max_clients=1):
        """
        初始化传输服务器
        
        Args:
            port: 监听端口
            max_clients: 最大客户端数量
        """
        self.port = port
        self.max_clients = max_clients
        
        # 创建UDP套接字
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        
        # 尝试绑定端口，如果被占用则尝试其他端口
        max_attempts = 10
        for attempt in range(max_attempts):
            try:
                self.socket.bind(('0.0.0.0', self.port))
                print(f"Successfully bound to port {self.port}")
                break
            except OSError as e:
                if attempt < max_attempts - 1:
                    print(f"Port {self.port} is in use, trying port {self.port + 1}")
                    self.port += 1
                else:
                    raise e
        
        # 客户端列表
        self.clients = {}  # (addr, port) -> client_info
        
        # 数据队列
        self.send_queue = queue.Queue(maxsize=1000)
        self.receive_queue = queue.Queue(maxsize=100)
        
        # 控制标志
        self.is_running = False
        
        # 线程
        self.receive_thread = None
        self.send_thread = None
        
        # 网络监控
        self.network_monitor = NetworkMonitor()
        
        # 序列号
        self.next_seq_num = 0
        
        # FEC控制
        self.fec_enabled = True
        self.fec_block_size = 8  # 每个FEC块包含的数据包数
        self.fec_overhead = 0.2  # FEC开销(额外的冗余包比例)
        
        # 缓冲区，用于FEC计算
        self.fec_buffer = []
        
        # 统计信息
        self.stats = {
            "sent_packets": 0,
            "sent_bytes": 0,
            "received_packets": 0,
            "received_bytes": 0
        }
    
    def start(self):
        """启动服务器"""
        if self.is_running:
            return
        
        # 如果socket为None，重新创建
        if self.socket is None:
            try:
                self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                self.socket.bind(('0.0.0.0', self.port))
            except Exception as e:
                print(f"Error creating socket: {e}")
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
        
        print(f"Transport server started on port {self.port}")
    
    def stop(self):
        """停止服务器"""
        self.is_running = False
        
        if self.receive_thread:
            self.receive_thread.join(timeout=1.0)
            self.receive_thread = None
        
        if self.send_thread:
            self.send_thread.join(timeout=1.0)
            self.send_thread = None
        
        if self.socket:
            self.socket.close()
            self.socket = None
        
        print("Transport server stopped")
    
    def send_video_frame(self, frame_data, frame_index, is_keyframe, width, height, encoding_params=None):
        """
        发送视频帧
        
        Args:
            frame_data: 帧数据(字节)
            frame_index: 帧索引
            is_keyframe: 是否是关键帧
            width: 帧宽度
            height: 帧高度
            encoding_params: 编码参数
        """
        if not self.clients:
            return False
        
        # 根据网络状况调整分片大小
        network_stats = self.network_monitor.get_current_stats()
        max_payload_size = self._calculate_optimal_payload_size(network_stats)
        
        # 创建标志
        flags = 0
        if is_keyframe:
            flags |= VideoPacket.FLAG_KEYFRAME
        
        # 分片大帧
        fragments = fragment_video_frame(
            frame_data, frame_index, time.time(), is_keyframe,
            max_payload_size, self.next_seq_num
        )
        
        # 更新序列号
        self.next_seq_num += len(fragments)
        
        # 将分片放入发送队列
        for fragment in fragments:
            self._queue_packet(fragment)
        
        # 生成并发送FEC包(如果启用)
        if self.fec_enabled and fragments:
            self._generate_fec_packets(fragments)
        
        return True
    
    def _calculate_optimal_payload_size(self, network_stats):
        """
        计算最优的有效载荷大小
        
        Args:
            network_stats: 网络统计信息
            
        Returns:
            最优的有效载荷大小(字节)
        """
        # 基础大小
        base_size = 1200
        
        # 根据丢包率调整
        loss_factor = 1.0 - min(0.5, network_stats["packet_loss"] * 5)  # 最多减少50%
        
        # 根据RTT调整
        rtt_factor = 1.0
        if network_stats["rtt"] > 200:
            # RTT较高时减小包大小
            rtt_factor = max(0.7, 1.0 - (network_stats["rtt"] - 200) / 1000)
        
        # 计算最终大小
        optimal_size = int(base_size * loss_factor * rtt_factor)
        
        # 限制在合理范围内
        return max(500, min(1400, optimal_size))
    
    def _generate_fec_packets(self, packets):
        """
        为数据包生成FEC包
        
        Args:
            packets: 数据包列表
        """
        # 将包添加到FEC缓冲区
        self.fec_buffer.extend(packets)
        
        # 当缓冲区达到FEC块大小时生成FEC包
        while len(self.fec_buffer) >= self.fec_block_size:
            # 取出一个块的数据包
            block = self.fec_buffer[:self.fec_block_size]
            self.fec_buffer = self.fec_buffer[self.fec_block_size:]
            
            # 计算要生成的FEC包数量
            fec_count = max(1, int(self.fec_block_size * self.fec_overhead))
            
            # 生成FEC包
            for i in range(fec_count):
                fec_packet = FECPacket(
                    seq_num=self.next_seq_num,
                    block_index=block[0].seq_num // self.fec_block_size,
                    timestamp=time.time(),
                    source_packets=block
                )
                self.next_seq_num += 1
                
                # 将FEC包放入发送队列
                self._queue_packet(fec_packet)
    
    def _queue_packet(self, packet):
        """
        将数据包放入发送队列
        
        Args:
            packet: 要发送的数据包
        """
        try:
            # 放入发送队列
            self.send_queue.put(packet, block=False)
            return True
        except:
            return False
    
    def _send_loop(self):
        """发送线程主循环"""
        while self.is_running:
            # 检查是否有客户端
            if not self.clients:
                print("等待客户端连接...")
                time.sleep(1.0)  # 等待更长时间
                continue
            
            try:
                # 从队列获取要发送的数据包
                packet = self.send_queue.get(block=True, timeout=0.1)
            except:
                continue
            
            # 序列化数据包
            packet_data = packet.serialize()
            
            # 记录发送统计
            self.stats["sent_packets"] += 1
            self.stats["sent_bytes"] += len(packet_data)
            
            # 记录到网络监控
            self.network_monitor.packet_sent(packet)
            
            # 发送到所有客户端
            for client_addr, client_info in list(self.clients.items()):
                try:
                    self.socket.sendto(packet_data, client_addr)
                    print(f"发送数据包到 {client_addr}: {len(packet_data)} 字节")
                except Exception as e:
                    print(f"发送到 {client_addr} 失败: {e}")
                    # 移除无法访问的客户端
                    self.clients.pop(client_addr, None)
    
    def _receive_loop(self):
        """接收线程主循环"""
        while self.is_running:
            try:
                # 设置超时以便定期检查is_running标志
                self.socket.settimeout(0.1)
                
                # 接收数据
                data, addr = self.socket.recvfrom(2048)
                
                # 解析数据包
                packet = Packet.deserialize(data)
                
                if packet:
                    # 记录接收统计
                    self.stats["received_packets"] += 1
                    self.stats["received_bytes"] += len(data)
                    
                    # 处理不同类型的包
                    if packet.packet_type == PACKET_TYPE_CONTROL:
                        self._handle_control_packet(packet, addr)
                    elif packet.packet_type == PACKET_TYPE_HEARTBEAT:
                        self._handle_heartbeat_packet(packet, addr)
                    
                    # 将包放入接收队列
                    try:
                        self.receive_queue.put((packet, addr), block=False)
                    except:
                        pass
                    
                    # 记录到网络监控
                    self.network_monitor.packet_received(packet)
            except socket.timeout:
                continue
            except Exception as e:
                print(f"Error in receive loop: {e}")
                time.sleep(0.01)
    
    def _handle_control_packet(self, packet, addr):
        """
        处理控制包
        
        Args:
            packet: 控制包
            addr: 客户端地址
        """
        if isinstance(packet, ControlPacket):
            # 根据控制类型处理
            if packet.ctrl_type == ControlPacket.CTRL_TYPE_ACK:
                # 处理ACK
                pass
            elif packet.ctrl_type == ControlPacket.CTRL_TYPE_NACK:
                # 处理NACK(重传请求)
                self._handle_nack(packet, addr)
            elif packet.ctrl_type == ControlPacket.CTRL_TYPE_STATS:
                # 处理客户端统计信息
                self._handle_client_stats(packet, addr)
            
            # 将客户端添加到列表中(如果不存在)
            if addr not in self.clients:
                self.clients[addr] = {
                    "last_seen": time.time(),
                    "stats": {}
                }
                print(f"新客户端连接(通过控制包): {addr}")
            else:
                # 更新最后活动时间
                self.clients[addr]["last_seen"] = time.time()
    
    def _handle_heartbeat_packet(self, packet, addr):
        """
        处理心跳包
        
        Args:
            packet: 心跳包
            addr: 客户端地址
        """
        if isinstance(packet, HeartbeatPacket):
            # 提取客户端统计信息
            client_stats = packet.client_stats
            
            # 将客户端添加到列表中(如果不存在)
            if addr not in self.clients:
                self.clients[addr] = {
                    "last_seen": time.time(),
                    "stats": client_stats
                }
                print(f"新客户端连接: {addr}")
            else:
                # 更新客户端信息
                self.clients[addr]["last_seen"] = time.time()
                self.clients[addr]["stats"].update(client_stats)
            
            # 发送心跳响应
            response = HeartbeatPacket(
                seq_num=self.next_seq_num,
                timestamp=time.time(),
                client_stats=self.network_monitor.get_current_stats()
            )
            self.next_seq_num += 1
            
            # 序列化并发送
            response_data = response.serialize()
            try:
                self.socket.sendto(response_data, addr)
                print(f"发送心跳响应到 {addr}")
            except Exception as e:
                print(f"发送心跳响应失败: {e}")
    
    def _handle_nack(self, packet, addr):
        """
        处理NACK(负确认，请求重传)
        
        Args:
            packet: NACK包
            addr: 客户端地址
        """
        if not hasattr(packet, 'ctrl_data') or not packet.ctrl_data:
            return
        
        # 获取需要重传的序列号列表
        missing_seqs = packet.ctrl_data.get("missing_seqs", [])
        
        if not missing_seqs:
            return
        
        # TODO: 实现重传逻辑
        # 在实际实现中，我们需要维护一个已发送包的缓存
        # 用于重传丢失的包
        
        print(f"Received NACK for {len(missing_seqs)} packets")
    
    def _handle_client_stats(self, packet, addr):
        """
        处理客户端统计信息
        
        Args:
            packet: 统计包
            addr: 客户端地址
        """
        if not hasattr(packet, 'ctrl_data') or not packet.ctrl_data:
            return
        
        # 提取客户端统计信息
        client_stats = packet.ctrl_data
        
        # 更新客户端信息
        if addr in self.clients:
            self.clients[addr]["stats"].update(client_stats)
        
        # 将统计信息传递给网络监控
        # 可以用于调整编码和传输参数
        if "rtt" in client_stats and "packet_loss" in client_stats:
            self.network_monitor.update_from_client({
                "rtt": client_stats["rtt"],
                "packet_loss": client_stats["packet_loss"],
                "bandwidth": client_stats.get("bandwidth", 0)
            })
    
    def get_client_count(self):
        """获取当前客户端数量"""
        return len(self.clients)
    
    def get_network_stats(self):
        """获取网络统计信息"""
        return self.network_monitor.get_current_stats()