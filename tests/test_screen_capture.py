import pytest
import numpy as np
import time
import logging
from server.screen_capture import ScreenCapturer


@pytest.fixture
def screen_capturer():
    capturer = ScreenCapturer(capture_rate=30)
    capturer.start()
    yield capturer
    capturer.stop()


def test_screen_capturer_initialization():
    """测试屏幕捕获器初始化"""
    capturer = ScreenCapturer()
    width, height = capturer.get_monitor_size()

    assert width > 0
    assert height > 0
    assert capturer.capture_rate == 30  # 默认值
    assert not capturer.running


def test_invalid_parameters():
    """测试无效参数处理"""
    # 测试无效的显示器编号
    with pytest.raises(ValueError, match="monitor_number必须大于等于1"):
        ScreenCapturer(monitor_number=0)
    
    # 测试无效的帧率
    with pytest.raises(ValueError, match="capture_rate必须在1-120之间"):
        ScreenCapturer(capture_rate=0)
    
    with pytest.raises(ValueError, match="capture_rate必须在1-120之间"):
        ScreenCapturer(capture_rate=121)


def test_capture_frame(screen_capturer):
    """测试帧捕获功能"""
    frame = screen_capturer.capture_frame()

    # 检查返回的帧是否是numpy数组
    assert isinstance(frame, np.ndarray)

    # 检查形状是否匹配显示器尺寸
    width, height = screen_capturer.get_monitor_size()
    assert frame.shape[0] == height
    assert frame.shape[1] == width
    assert frame.shape[2] == 4  # BGRA格式


def test_frame_rate_control(screen_capturer):
    """测试帧率控制"""
    # 捕获第一帧
    frame1 = screen_capturer.capture_frame()

    # 立即捕获第二帧，应该返回相同的帧(因为帧率限制)
    frame2 = screen_capturer.capture_frame()

    # 两帧应该是相同的对象
    assert frame1 is frame2

    # 等待足够长的时间以允许捕获新帧
    time.sleep(1.0 / screen_capturer.capture_rate + 0.01)

    # 现在应该能够捕获新帧
    frame3 = screen_capturer.capture_frame()
    assert frame1 is not frame3


def test_get_mouse_position(screen_capturer):
    """测试鼠标位置获取"""
    x, y = screen_capturer.get_mouse_position()

    # 坐标应该是有效的整数
    assert isinstance(x, int)
    assert isinstance(y, int)

    # 坐标应该在屏幕范围内
    width, height = screen_capturer.get_monitor_size()
    assert 0 <= x <= width
    assert 0 <= y <= height


def test_start_stop_behavior():
    """测试启动和停止行为"""
    capturer = ScreenCapturer()
    
    # 测试重复启动
    capturer.start()
    assert capturer.running is True
    
    capturer.start()  # 应该不会报错，只是警告
    assert capturer.running is True
    
    # 测试停止
    capturer.stop()
    assert capturer.running is False
    
    # 测试重复停止
    capturer.stop()  # 应该不会报错，只是警告
    assert capturer.running is False


def test_error_handling():
    """测试错误处理"""
    capturer = ScreenCapturer()
    capturer.start()
    
    # 正常捕获应该成功
    frame = capturer.capture_frame()
    assert frame is not None


def test_thread_safety():
    """测试线程安全性"""
    import threading
    
    capturer = ScreenCapturer()
    capturer.start()
    
    frames = []
    errors = []
    
    def capture_worker():
        try:
            for _ in range(10):
                frame = capturer.capture_frame()
                frames.append(frame)
                time.sleep(0.01)
        except Exception as e:
            errors.append(e)
    
    # 创建多个线程同时捕获
    threads = []
    for _ in range(3):
        thread = threading.Thread(target=capture_worker)
        threads.append(thread)
        thread.start()
    
    # 等待所有线程完成
    for thread in threads:
        thread.join()
    
    # 验证没有错误发生
    assert len(errors) == 0
    assert len(frames) == 30  # 3个线程 * 10次捕获