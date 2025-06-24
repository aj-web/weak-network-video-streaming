import pytest
import threading
import time
from unittest.mock import MagicMock, patch
import numpy as np

from server.main import VideoStreamingServer


@pytest.fixture
def mock_modules():
    """模拟各功能模块"""
    with patch("server.main.ScreenCapturer") as mock_capturer, \
            patch("server.main.ROIDetector") as mock_detector, \
            patch("server.main.VideoEncoder") as mock_encoder, \
            patch("server.main.QuicServer") as mock_server:
        # 设置模拟屏幕捕获器
        mock_capturer.return_value.get_monitor_size.return_value = (1920, 1080)
        mock_capturer.return_value.capture_frame.return_value = np.zeros((1080, 1920, 3), dtype=np.uint8)
        mock_capturer.return_value.get_mouse_position.return_value = (960, 540)

        # 设置模拟ROI检测器
        mock_detector.return_value.detect_roi.return_value = {
            'x': 100, 'y': 100, 'width': 200, 'height': 200, 'importance': 1.0
        }

        # 设置模拟视频编码器
        mock_encoder.return_value.encode_frame.return_value = True

        # 设置模拟QUIC服务器
        mock_server.return_value.start = MagicMock()
        mock_server.return_value.stop = MagicMock()

        yield {
            'capturer': mock_capturer,
            'detector': mock_detector,
            'encoder': mock_encoder,
            'server': mock_server
        }


def test_server_initialization(mock_modules):
    """测试服务器初始化"""
    server = VideoStreamingServer(
        host="127.0.0.1",
        port=4433,
        fps=60,
        bitrate=5000000,
        use_roi=True
    )

    # 验证服务器属性
    assert server.host == "127.0.0.1"
    assert server.port == 4433
    assert server.fps == 60
    assert server.bitrate == 5000000
    assert server.use_roi is True
    assert not server.running

    # 验证模块初始化
    mock_modules['capturer'].assert_called_once()
    mock_modules['detector'].assert_called_once_with(frame_width=1920, frame_height=1080)
    mock_modules['encoder'].assert_called_once_with(
        width=1920, height=1080, fps=60, bitrate=5000000, use_roi=True
    )
    mock_modules['server'].assert_called_once_with(host="127.0.0.1", port=4433)


@patch("threading.Thread")
def test_server_start_stop(mock_thread, mock_modules):
    """测试服务器启动和停止"""
    server = VideoStreamingServer()

    # 启动服务器
    server.start()

    # 验证状态
    assert server.running

    # 验证线程启动
    assert mock_thread.call_count == 2

    # 停止服务器
    server.stop()

    # 验证状态
    assert not server.running


def test_network_status_callback(mock_modules):
    """测试网络状态回调处理"""
    server = VideoStreamingServer()

    # 模拟网络状态更新
    network_status = {
        'rtt': 100,
        'packet_loss': 2.5,
        'bandwidth': 4000000
    }

    # 调用回调
    with patch.object(server, '_adjust_encoding_params') as mock_adjust:
        server._on_network_status_update(network_status)

        # 验证调整函数被调用
        mock_adjust.assert_called_once_with(100, 2.5, 4000000)


def test_encoding_params_adjustment(mock_modules):
    """测试编码参数调整"""
    server = VideoStreamingServer()

    # 测试带宽调整
    server._adjust_encoding_params(50, 1.0, 5000000)
    server.video_encoder.adjust_bitrate.assert_called_with(4000000)  # 80%的带宽

    # 测试低丢包率的GOP调整
    server.video_encoder.adjust_gop_size.assert_called_with(30)

    # 测试中等丢包率的GOP调整
    server._adjust_encoding_params(50, 3.0, 5000000)
    server.video_encoder.adjust_gop_size.assert_called_with(20)

    # 测试高丢包率的GOP调整
    server._adjust_encoding_params(50, 6.0, 5000000)
    server.video_encoder.adjust_gop_size.assert_called_with(15)


@patch("time.sleep", return_value=None)  # 避免实际睡眠
def test_main_loop(mock_sleep, mock_modules):
    """测试主循环功能"""
    server = VideoStreamingServer()

    # 模拟运行状态
    server.running = True

    # 创建一个会在几次迭代后停止服务器的函数
    iteration_count = [0]

    def stop_after_iterations(*args, **kwargs):
        iteration_count[0] += 1
        if iteration_count[0] >= 3:
            server.running = False
        return np.zeros((1080, 1920, 3), dtype=np.uint8)

    # 替换capture_frame方法
    server.screen_capturer.capture_frame = stop_after_iterations

    # 运行主循环
    server._main_loop()

    # 验证各模块方法被调用
    assert server.screen_capturer.start.called
    assert server.video_encoder.start.called
    assert server.screen_capturer.get_mouse_position.call_count == 3
    assert server.roi_detector.detect_roi.call_count == 3
    assert server.video_encoder.encode_frame.call_count == 3
    assert server.screen_capturer.stop.called
    assert server.video_encoder.stop.called