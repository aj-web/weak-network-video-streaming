import pytest
import numpy as np
import time
import threading
import logging
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
    assert encoder.roi_qp_offset == -5  # 默认值
    assert not encoder.running

    # 清理
    encoder.stop()


def test_invalid_parameters():
    """测试无效参数处理"""
    # 测试无效的宽度和高度
    with pytest.raises(ValueError, match="宽度和高度必须大于0"):
        VideoEncoder(width=0, height=480)
    
    with pytest.raises(ValueError, match="宽度和高度必须大于0"):
        VideoEncoder(width=640, height=-1)
    
    # 测试无效的帧率
    with pytest.raises(ValueError, match="帧率必须在1-120之间"):
        VideoEncoder(width=640, height=480, fps=0)
    
    with pytest.raises(ValueError, match="帧率必须在1-120之间"):
        VideoEncoder(width=640, height=480, fps=121)
    
    # 测试无效的码率
    with pytest.raises(ValueError, match="码率必须大于0"):
        VideoEncoder(width=640, height=480, bitrate=0)
    
    # 测试无效的GOP大小
    with pytest.raises(ValueError, match="GOP大小必须大于0"):
        VideoEncoder(width=640, height=480, gop_size=0)
    
    # 测试无效的ROI QP偏移
    with pytest.raises(ValueError, match="ROI QP偏移必须在-20到20之间"):
        VideoEncoder(width=640, height=480, roi_qp_offset=-21)
    
    with pytest.raises(ValueError, match="ROI QP偏移必须在-20到20之间"):
        VideoEncoder(width=640, height=480, roi_qp_offset=21)


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


def test_invalid_frame_encoding(video_encoder):
    """测试无效帧编码"""
    # 测试空帧
    success = video_encoder.encode_frame(None)
    assert not success
    
    # 测试尺寸不匹配的帧
    wrong_size_frame = np.zeros((320, 240, 3), dtype=np.uint8)
    success = video_encoder.encode_frame(wrong_size_frame)
    assert not success


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


def test_roi_encoding_with_different_importance(video_encoder, sample_frame):
    """测试不同重要性的ROI编码"""
    # 测试高重要性的ROI
    high_importance_roi = {
        'x': 100,
        'y': 100,
        'width': 200,
        'height': 200,
        'importance': 1.5
    }
    
    success = video_encoder.encode_frame(sample_frame, high_importance_roi)
    assert success
    
    # 测试低重要性的ROI
    low_importance_roi = {
        'x': 300,
        'y': 300,
        'width': 100,
        'height': 100,
        'importance': 0.5
    }
    
    success = video_encoder.encode_frame(sample_frame, low_importance_roi)
    assert success
    
    # 等待编码完成
    video_encoder.packet_queue.join()


def test_roi_encoder_with_custom_qp_offset():
    """测试自定义QP偏移的ROI编码器"""
    # 创建带有自定义QP偏移的编码器
    encoder = VideoEncoder(
        width=640, 
        height=480, 
        roi_qp_offset=-10  # 更高质量的ROI
    )
    encoder.start()
    
    assert encoder.roi_qp_offset == -10
    
    # 创建测试帧
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    roi_info = {'x': 100, 'y': 100, 'width': 200, 'height': 200, 'importance': 1.0}
    
    success = encoder.encode_frame(frame, roi_info)
    assert success
    
    encoder.stop()


def test_bitrate_adjustment(video_encoder):
    """测试码率调整"""
    initial_bitrate = video_encoder.bitrate

    # 调整码率
    new_bitrate = initial_bitrate * 1.5
    video_encoder.adjust_bitrate(int(new_bitrate))

    # 检查新码率
    assert video_encoder.bitrate == new_bitrate
    assert video_encoder.stream.bit_rate == new_bitrate
    
    # 测试无效码率
    video_encoder.adjust_bitrate(0)  # 应该被忽略
    assert video_encoder.bitrate == new_bitrate  # 应该保持不变


def test_gop_size_adjustment(video_encoder):
    """测试GOP大小调整"""
    initial_gop = video_encoder.gop_size
    
    # 调整GOP大小
    new_gop = 15
    video_encoder.adjust_gop_size(new_gop)
    
    assert video_encoder.gop_size == new_gop
    
    # 测试无效GOP大小
    video_encoder.adjust_gop_size(0)  # 应该被忽略
    assert video_encoder.gop_size == new_gop  # 应该保持不变


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


def test_get_current_settings(video_encoder):
    """测试获取当前设置"""
    settings = video_encoder.get_current_settings()
    
    assert 'width' in settings
    assert 'height' in settings
    assert 'fps' in settings
    assert 'codec' in settings
    assert 'bitrate' in settings
    assert 'gop_size' in settings
    assert 'use_roi' in settings
    assert 'roi_qp_offset' in settings
    assert 'encoding_fps' in settings
    
    assert settings['width'] == 640
    assert settings['height'] == 480
    assert settings['fps'] == 30
    assert settings['codec'] == 'h264'
    assert settings['use_roi'] is True
    assert settings['roi_qp_offset'] == -5


def test_frame_callback(video_encoder, sample_frame):
    """测试帧回调功能"""
    received_packets = []
    received_info = []
    
    def frame_callback(packet, frame_info):
        received_packets.append(packet)
        received_info.append(frame_info)
    
    # 设置回调
    video_encoder.frame_callback = frame_callback
    
    # 编码帧
    success = video_encoder.encode_frame(sample_frame)
    assert success
    
    # 等待编码完成
    video_encoder.packet_queue.join()
    time.sleep(0.1)  # 给回调一点时间
    
    # 检查是否收到回调
    assert len(received_packets) > 0
    assert len(received_info) > 0
    
    # 检查回调信息
    info = received_info[0]
    assert 'frame_count' in info
    assert 'timestamp' in info
    assert 'type' in info
    assert 'width' in info
    assert 'height' in info
    assert info['type'] == 'video_data'
    assert info['width'] == 640
    assert info['height'] == 480


def test_queue_overflow_handling():
    """测试队列溢出处理"""
    # 创建编码器，使用小队列
    encoder = VideoEncoder(width=640, height=480, fps=30, bitrate=2000000)
    encoder.packet_queue = queue.Queue(maxsize=2)  # 小队列
    encoder.start()
    
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    
    # 快速添加多个帧，应该有一些被丢弃
    results = []
    for _ in range(5):
        result = encoder.encode_frame(frame)
        results.append(result)
    
    # 应该有一些帧被丢弃
    assert False in results
    
    encoder.stop()


def test_thread_safety():
    """测试线程安全性"""
    encoder = VideoEncoder(width=640, height=480, fps=30, bitrate=2000000)
    encoder.start()
    
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    results = []
    errors = []
    
    def encode_worker():
        try:
            for _ in range(5):
                result = encoder.encode_frame(frame)
                results.append(result)
                time.sleep(0.01)
        except Exception as e:
            errors.append(e)
    
    # 创建多个线程同时编码
    threads = []
    for _ in range(3):
        thread = threading.Thread(target=encode_worker)
        threads.append(thread)
        thread.start()
    
    # 等待所有线程完成
    for thread in threads:
        thread.join()
    
    # 验证没有错误发生
    assert len(errors) == 0
    assert len(results) == 15  # 3个线程 * 5次编码
    
    encoder.stop()