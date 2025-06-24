import pytest
import numpy as np
import time
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