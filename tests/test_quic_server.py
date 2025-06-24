import pytest
import asyncio
import json
import os
import tempfile
from unittest.mock import MagicMock, patch
import time

from server.network.quic_server import VideoStreamProtocol, QuicServer


# 测试VideoStreamProtocol类
def test_video_stream_protocol_init():
    """测试协议处理器初始化"""
    protocol = VideoStreamProtocol()

    assert isinstance(protocol.connections, dict)
    assert protocol.next_packet_id == 0
    assert protocol.network_status_callback is None


def test_connection_management():
    """测试连接管理功能"""
    protocol = VideoStreamProtocol()

    # 测试连接建立
    protocol.connection_made("conn1")
    assert "conn1" in protocol.connections
    assert protocol.connections["conn1"]["id"] == "conn1"

    # 测试连接断开
    protocol.connection_lost("conn1")
    assert "conn1" not in protocol.connections


def test_process_stream_data():
    """测试流数据处理"""
    protocol = VideoStreamProtocol()

    # 模拟回调函数
    mock_callback = MagicMock()
    protocol.set_network_status_callback(mock_callback)

    # 建立连接
    protocol.connection_made("conn1")

    # 创建测试数据
    test_data = json.dumps({
        "type": "status",
        "rtt": 50,
        "packet_loss": 0.5,
        "bandwidth": 5000000
    }).encode('utf-8')

    # 处理数据
    response = protocol.process_stream_data("conn1", 1, test_data)

    # 验证响应
    assert response["type"] == "ack"
    assert "timestamp" in response

    # 验证连接状态更新
    assert protocol.connections["conn1"]["rtt"] == 50
    assert protocol.connections["conn1"]["packet_loss"] == 0.5
    assert protocol.connections["conn1"]["bandwidth"] == 5000000

    # 验证回调被调用
    mock_callback.assert_called_once()

    # 测试错误处理
    invalid_data = b"invalid json"
    response = protocol.process_stream_data("conn1", 1, invalid_data)
    assert response["type"] == "error"


def test_create_video_packet():
    """测试视频数据包创建"""
    protocol = VideoStreamProtocol()

    # 创建测试帧数据
    frame_data = b"test frame data"
    frame_info = {
        "keyframe": True,
        "width": 640,
        "height": 480
    }

    # 创建数据包
    packet, header = protocol.create_video_packet(frame_data, frame_info)

    # 验证包头
    assert header["id"] == 0  # 第一个包ID为0
    assert header["keyframe"] is True
    assert header["width"] == 640
    assert header["height"] == 480
    assert header["data_size"] == len(frame_data)

    # 验证包格式(应该包含头部长度+头部JSON+帧数据)
    assert len(packet) > len(frame_data)

    # 验证下一个包ID增加
    assert protocol.next_packet_id == 1


# 测试QuicServer类
@pytest.mark.asyncio
async def test_quic_server_init():
    """测试QUIC服务器初始化"""
    # 创建临时证书文件
    cert_file = tempfile.mktemp(suffix=".pem")
    key_file = tempfile.mktemp(suffix=".pem")

    # 写入一些测试数据
    with open(cert_file, "w") as f:
        f.write("TEST CERT")
    with open(key_file, "w") as f:
        f.write("TEST KEY")

    # 初始化服务器
    server = QuicServer(
        host="127.0.0.1",
        port=4433,
        cert_file=cert_file,
        key_file=key_file
    )

    assert server.host == "127.0.0.1"
    assert server.port == 4433
    assert server.cert_file == cert_file
    assert server.key_file == key_file
    assert isinstance(server.protocol, VideoStreamProtocol)
    assert not server.running

    # 清理临时文件
    os.remove(cert_file)
    os.remove(key_file)


@pytest.mark.asyncio
@patch("server.network.quic_server.serve")
async def test_quic_server_start_stop(mock_serve):
    """测试QUIC服务器启动和停止"""
    # 设置模拟服务器
    mock_server = MagicMock()
    mock_serve.return_value = mock_server

    # 创建临时证书文件
    cert_file = tempfile.mktemp(suffix=".pem")
    key_file = tempfile.mktemp(suffix=".pem")

    # 写入一些测试数据
    with open(cert_file, "w") as f:
        f.write("TEST CERT")
    with open(key_file, "w") as f:
        f.write("TEST KEY")

    # 初始化服务器
    server = QuicServer(
        host="127.0.0.1",
        port=4433,
        cert_file=cert_file,
        key_file=key_file
    )

    # 创建一个任务来启动服务器
    start_task = asyncio.create_task(server.start())

    # 等待服务器启动
    await asyncio.sleep(0.1)

    # 验证服务器状态
    assert server.running
    mock_serve.assert_called_once()

    # 停止服务器
    await server.stop()

    # 验证服务器状态
    assert not server.running
    mock_server.close.assert_called_once()
    mock_server.wait_closed.assert_called_once()

    # 取消启动任务
    start_task.cancel()
    try:
        await start_task
    except asyncio.CancelledError:
        pass

    # 清理临时文件
    os.remove(cert_file)
    os.remove(key_file)


def test_set_network_status_callback():
    """测试设置网络状态回调"""
    server = QuicServer()

    # 模拟回调函数
    mock_callback = MagicMock()
    server.set_network_status_callback(mock_callback)

    # 验证回调设置
    assert server.protocol.network_status_callback == mock_callback