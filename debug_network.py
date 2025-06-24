#!/usr/bin/env python3
# debug_network.py

import socket
import time
import threading
import sys
import os

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from common.network_utils.protocol import *

def test_server():
    """测试服务端"""
    print("启动测试服务端...")
    
    # 创建UDP套接字
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server_socket.bind(('0.0.0.0', 8000))
    server_socket.settimeout(1.0)
    
    print("服务端监听在 0.0.0.0:8000")
    
    clients = set()
    next_seq_num = 1
    
    try:
        while True:
            try:
                # 接收数据
                data, addr = server_socket.recvfrom(2048)
                print(f"收到来自 {addr} 的数据: {len(data)} 字节")
                
                # 解析数据包
                packet = Packet.deserialize(data)
                if packet:
                    print(f"  包类型: {packet.packet_type}")
                    print(f"  序列号: {packet.seq_num}")
                    print(f"  时间戳: {packet.timestamp}")
                    
                    if packet.packet_type == PACKET_TYPE_HEARTBEAT:
                        clients.add(addr)
                        print(f"  心跳包，客户端 {addr} 已连接")
                        
                        # 发送心跳响应
                        response = HeartbeatPacket(
                            seq_num=next_seq_num,
                            timestamp=time.time(),
                            client_stats={"server_time": time.time()}
                        )
                        next_seq_num += 1
                        response_data = response.serialize()
                        server_socket.sendto(response_data, addr)
                        print(f"  发送心跳响应到 {addr}")
                    
                    elif packet.packet_type == PACKET_TYPE_VIDEO:
                        print(f"  视频包，帧索引: {packet.frame_index}")
                        print(f"  分片: {packet.fragment_index}/{packet.total_fragments}")
                
                # 发送测试视频包
                if clients:
                    test_frame_data = b"test_video_frame_data" * 100  # 模拟视频数据
                    fragments = fragment_video_frame(
                        test_frame_data, 
                        frame_index=1, 
                        timestamp=time.time(), 
                        is_keyframe=True,
                        max_payload_size=1000,
                        seq_start=next_seq_num
                    )
                    next_seq_num += len(fragments)
                    
                    for fragment in fragments:
                        packet_data = fragment.serialize()
                        for client_addr in clients:
                            server_socket.sendto(packet_data, client_addr)
                            print(f"发送视频分片到 {client_addr}: {len(packet_data)} 字节")
                    
                    time.sleep(1)  # 每秒发送一次
                
            except socket.timeout:
                continue
            except Exception as e:
                print(f"服务端错误: {e}")
                import traceback
                traceback.print_exc()
                continue
                
    except KeyboardInterrupt:
        print("\n服务端停止")
    finally:
        server_socket.close()

def test_client():
    """测试客户端"""
    print("启动测试客户端...")
    
    # 创建UDP套接字
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    client_socket.bind(('0.0.0.0', 0))  # 绑定任意端口
    client_socket.settimeout(1.0)
    
    server_addr = ('127.0.0.1', 8000)
    next_seq_num = 1
    
    # 发送心跳包
    heartbeat = HeartbeatPacket(
        seq_num=next_seq_num,
        timestamp=time.time(),
        client_stats={"client_time": time.time()}
    )
    next_seq_num += 1
    heartbeat_data = heartbeat.serialize()
    client_socket.sendto(heartbeat_data, server_addr)
    print(f"发送心跳包到 {server_addr}")
    
    try:
        while True:
            try:
                # 接收数据
                data, addr = client_socket.recvfrom(4096)
                print(f"收到来自 {addr} 的数据: {len(data)} 字节")
                
                # 解析数据包
                packet = Packet.deserialize(data)
                if packet:
                    print(f"  包类型: {packet.packet_type}")
                    print(f"  序列号: {packet.seq_num}")
                    print(f"  时间戳: {packet.timestamp}")
                    
                    if packet.packet_type == PACKET_TYPE_HEARTBEAT:
                        print(f"  心跳响应")
                    elif packet.packet_type == PACKET_TYPE_VIDEO:
                        print(f"  视频包，帧索引: {packet.frame_index}")
                        print(f"  分片: {packet.fragment_index}/{packet.total_fragments}")
                        print(f"  数据大小: {len(packet.payload)} 字节")
                
            except socket.timeout:
                # 定期发送心跳包
                heartbeat = HeartbeatPacket(
                    seq_num=next_seq_num,
                    timestamp=time.time(),
                    client_stats={"client_time": time.time()}
                )
                next_seq_num += 1
                heartbeat_data = heartbeat.serialize()
                client_socket.sendto(heartbeat_data, server_addr)
                print(f"发送心跳包到 {server_addr}")
                continue
            except Exception as e:
                print(f"客户端错误: {e}")
                import traceback
                traceback.print_exc()
                continue
                
    except KeyboardInterrupt:
        print("\n客户端停止")
    finally:
        client_socket.close()

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "server":
        test_server()
    elif len(sys.argv) > 1 and sys.argv[1] == "client":
        test_client()
    else:
        print("用法:")
        print("  python debug_network.py server  # 启动测试服务端")
        print("  python debug_network.py client  # 启动测试客户端") 