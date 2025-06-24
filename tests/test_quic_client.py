import pytest
import asyncio
import json
import os
import sys
import tempfile
from unittest.mock import MagicMock, patch
import time
import threading

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from client.network.quic_client import VideoStreamClient, QuicClientProtocol


# 基本测试: 初始化客户端
def test_client_initialization():
    """测试客户端初始化"""
    client = VideoStreamClient(host="127.0.0.1", port=4433)

    assert client.host == "127.0.0.1"
    assert client.port == 4433
    assert not client.verify_ssl
    assert not client.connected
    assert client.connection is None

    # 检查统计信息初始化
    stats = client.get_connection_stats()
    assert stats['bytes_received'] == 0
    assert stats['packets_received'] == 0
    assert stats['rtt'] == 0
    assert stats['bandwidth'] == 0


# 测试回调设置
def test_client_callbacks():
    """测试客户端回调设置"""
    client = VideoStreamClient()

    # 测试视频帧回调
    mock_frame_callback = MagicMock()
    client.set_video_frame_callback(mock_frame_callback)
    assert client.video_frame_callback == mock_frame_callback

    # 测试连接状态回调
    mock_status_callback = MagicMock()
    client.set_connection_status_callback(mock_status_callback)
    assert client.connection_status_callback == mock_status_callback


# 测试数据处理
def test_handle_video_frame():
    """测试视频帧处理"""
    client = VideoStreamClient()

    # 模拟帧数据和信息
    frame_data = b"test_frame_data"
    frame_info = {
        'frame_id': 1,
        'timestamp': time.time(),
        'is_keyframe': True
    }

    # 设置回调
    mock_callback = MagicMock()
    client.set_video_frame_callback(mock_callback)

    # 调用回调
    client._on_video_frame(frame_data, frame_info)

    # 验证回调被调用
    mock_callback.assert_called_once_with(frame_data, frame_info)

    # 验证统计信息更新
    stats = client.get_connection_stats()
    assert stats['bytes_received'] == len(frame_data)
    assert stats['packets_received'] == 1

    # 验证队列
    frame = client.get_next_video_frame(timeout=0.1)
    assert frame is not None
    assert frame[0] == frame_data
    assert frame[1] == frame_info


# 测试协议处理器
def test_quic_client_protocol():
    """测试QUIC客户端协议处理器"""
    protocol = QuicClientProtocol()

    # 设置视频帧回调
    mock_callback = MagicMock()
    protocol.video_frame_callback = mock_callback

    # 创建测试视频数据包
    frame_data = b"test_frame_data"
    header = {
        'type': 'video_data',
        'frame_id': 1,
        'timestamp': int(time.time() * 1000),
        'is_keyframe': True,
        'width': 1280,
        'height': 720,
        'data_size': len(frame_data),
        'total_fragments': 1,
        'fragment_index': 0
    }

    # 序列化头部
    header_json = json.dumps(header).encode('utf-8')
    header_len = len(header_json)

    # 创建数据包
    packet = bytearray(4)  # 为头部长度预留空间
    packet[0:4] = header_len.to_bytes(4, byteorder='big')
    packet.extend(header_json)
    packet.extend(frame_data)

    # 模拟流数据接收
    protocol._handle_stream_data(1, bytes(packet), False)

    # 验证回调被调用
    mock_callback.assert_called_once()
    assert mock_callback.call_args[0][0] == frame_data  # 第一个参数是帧数据


# 集成测试: 客户端连接(需要本地运行服务端)
@pytest.mark.asyncio
@pytest.mark.skip(reason="需要运行服务端")
async def test_client_connect():
    """测试客户端连接到服务端"""
    client = VideoStreamClient(host="127.0.0.1", port=4433)

    # 设置连接状态回调
    connection_events = []

    def on_connection_status(status):
        connection_events.append(status)

    client.set_connection_status_callback(on_connection_status)

    # 启动连接(在单独的线程中)
    connect_task = asyncio.create_task(client.connect())

    # 等待连接建立或超时
    try:
        for _ in range(10):  # 最多等待10秒
            await asyncio.sleep(1)
            if client.connected:
                break

        # 检查连接状态
        assert client.connected
        assert client.connection is not None

        # 检查回调事件
        assert len(connection_events) > 0
        assert connection_events[0]['status'] == 'connected'

    finally:
        # 断开连接
        client.disconnect()

        # 取消任务
        connect_task.cancel()
        try:
            await connect_task
        except asyncio.CancelledError:
            pass