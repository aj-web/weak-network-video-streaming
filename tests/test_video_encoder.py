import pytest
import numpy as np
import time
import threading
from server.video_encoder import VideoEncoder


@pytest.fixture
def video_encoder():
    """创建一个基本的视频编码器实例"""
    encoder = VideoEncoder(width=640, height=480, fps=30, bitrate=2000000)
    encoder.start()
    yield encoder
    encoder.stop()


@pytest.fixture
def sample_frame():
    """创建一个样例视频帧"""
    # 创建一个640x480的彩色图像，带有简单的图案
    frame = np.zeros((480, 640, 3), dtype=np.uint8)

    # 添加一些颜色和形状
    frame[100:200, 100:200, 0] = 255  # 红色方块
    frame[200:300, 300:400, 1] = 255  # 绿色方块
    frame[300:400, 500:600, 2] = 255  # 蓝色方块

    return frame


def test_encoder_initialization():
    """测试编码器初始化"""
    encoder = VideoEncoder(1280, 720, fps=60, bitrate=5000000)

    assert encoder.width == 1280
    assert encoder.height == 720
    assert encoder.fps == 60
    assert encoder.bitrate == 5000000
    assert encoder.gop_size == 30  # 默认值
    assert encoder.use_roi is True  # 默认值
    assert not encoder.running

    # 清理
    encoder.stop()


def test_encoder_start_stop(video_encoder):
    """测试编码器启动和停止"""
    assert video_encoder.running
    assert video_encoder.encode_thread is not None
    assert video_encoder.encode_thread.is_alive()

    video_encoder.stop()

    assert not video_encoder.running
    # 线程应该已经结束
    time.sleep(0.2)  # 给线程一点时间结束
    assert not video_encoder.encode_thread.is_alive()


def test_frame_encoding(video_encoder, sample_frame):
    """测试帧编码功能"""
    # 编码一个帧
    success = video_encoder.encode_frame(sample_frame)
    assert success

    # 检查是否更新了帧计数
    assert video_encoder.frame_count == 1

    # 等待编码完成
    video_encoder.packet_queue.join()

    # 应该能够继续编码
    success = video_encoder.encode_frame(sample_frame)
    assert success


def test_roi_encoding(video_encoder, sample_frame):
    """测试ROI编码功能"""
    # 创建一个ROI信息
    roi_info = {
        'x': 100,
        'y': 100,
        'width': 200,
        'height': 200,
        'importance': 1.0
    }

    # 编码一个带ROI的帧
    success = video_encoder.encode_frame(sample_frame, roi_info)
    assert success

    # 等待编码完成
    video_encoder.packet_queue.join()


def test_bitrate_adjustment(video_encoder):
    """测试码率调整"""
    initial_bitrate = video_encoder.bitrate

    # 调整码率
    new_bitrate = initial_bitrate * 1.5
    video_encoder.adjust_bitrate(int(new_bitrate))

    # 检查新码率
    assert video_encoder.bitrate == new_bitrate
    assert video_encoder.stream.bit_rate == new_bitrate


def test_encoding_performance(video_encoder, sample_frame):
    """测试编码性能"""
    # 编码多个帧以测试性能
    num_frames = 10

    start_time = time.time()

    for _ in range(num_frames):
        video_encoder.encode_frame(sample_frame)

    # 等待编码完成
    video_encoder.packet_queue.join()

    elapsed = time.time() - start_time
    fps = num_frames / elapsed

    # 确保编码速度合理(应该比实时帧率快)
    assert fps > video_encoder.fps * 0.5