import sys
import os
import time
import logging
import threading
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from server.screen_capture import ScreenCapturer
from server.roi_detector import ROIDetector
from server.video_encoder import VideoEncoder
import cv2
import numpy as np

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("server_test")


def test_screen_capture():
    """测试屏幕捕获功能"""
    logger.info("======= 测试屏幕捕获 =======")

    capturer = ScreenCapturer(capture_rate=10)
    capturer.start()

    # 获取并保存几帧
    save_dir = Path("test_output")
    save_dir.mkdir(exist_ok=True)

    logger.info(f"捕获5帧并保存到 {save_dir}")

    for i in range(5):
        frame = capturer.capture_frame()

        # 获取鼠标位置
        mouse_x, mouse_y = capturer.get_mouse_position()
        logger.info(f"帧 #{i + 1} - 鼠标位置: ({mouse_x}, {mouse_y})")

        # 在帧上标记鼠标位置
        cv2.circle(frame, (mouse_x, mouse_y), 20, (0, 0, 255), 2)

        # 保存帧
        cv2.imwrite(str(save_dir / f"frame_{i + 1}.png"), frame)

        # 等待一点时间
        time.sleep(0.5)

    capturer.stop()
    logger.info(f"帧率: {capturer.get_current_fps():.2f} fps")
    logger.info("屏幕捕获测试完成")
    return True


def test_roi_detection():
    """测试ROI检测功能"""
    logger.info("======= 测试ROI检测 =======")

    # 创建屏幕捕获器和ROI检测器
    capturer = ScreenCapturer(capture_rate=10)
    width, height = capturer.get_monitor_size()
    detector = ROIDetector(frame_width=width, frame_height=height, roi_size=300)

    capturer.start()

    # 保存目录
    save_dir = Path("test_output")
    save_dir.mkdir(exist_ok=True)

    logger.info(f"检测3帧的ROI并保存到 {save_dir}")

    for i in range(3):
        # 捕获帧
        frame = capturer.capture_frame()

        # 获取鼠标位置
        mouse_pos = capturer.get_mouse_position()

        # 检测ROI
        roi_info = detector.detect_roi(frame, mouse_pos)
        logger.info(
            f"帧 #{i + 1} - ROI: x={roi_info['x']}, y={roi_info['y']}, width={roi_info['width']}, height={roi_info['height']}")

        # 绘制ROI区域
        result_frame = detector.draw_roi(frame)

        # 保存结果
        cv2.imwrite(str(save_dir / f"roi_{i + 1}.png"), result_frame)

        # 等待一点时间
        time.sleep(1.0)

    capturer.stop()
    logger.info("ROI检测测试完成")
    return True


def test_video_encoding():
    """测试视频编码功能"""
    logger.info("======= 测试视频编码 =======")

    # 创建屏幕捕获器和编码器
    capturer = ScreenCapturer(capture_rate=15)
    width, height = capturer.get_monitor_size()

    # 用于保存编码数据的列表
    encoded_frames = []

    # 编码回调函数
    def on_frame_encoded(frame_data, frame_info):
        logger.info(f"编码帧回调: {len(frame_data)} 字节, 帧 #{frame_info['frame_count']}")
        encoded_frames.append((frame_data, frame_info))

    # 创建编码器
    encoder = VideoEncoder(
        width=width,
        height=height,
        fps=15,
        bitrate=2000000,  # 2 Mbps
        use_roi=True,
        frame_callback=on_frame_encoded
    )

    capturer.start()
    encoder.start()

    # 编码10帧
    logger.info("编码10帧...")

    roi_detector = ROIDetector(frame_width=width, frame_height=height)

    for i in range(10):
        # 捕获帧
        frame = capturer.capture_frame()

        # 获取鼠标位置并检测ROI
        mouse_pos = capturer.get_mouse_position()
        roi_info = roi_detector.detect_roi(frame, mouse_pos)

        # 编码帧
        success = encoder.encode_frame(frame, roi_info)
        logger.info(f"帧 #{i + 1} 编码状态: {'成功' if success else '失败'}")

        # 等待一点时间
        time.sleep(0.2)

    # 等待编码完成
    time.sleep(1.0)

    capturer.stop()
    encoder.stop()

    # 检查编码结果
    logger.info(f"成功编码 {len(encoded_frames)} 帧")

    # 将第一帧保存到文件(仅用于验证有数据生成)
    if encoded_frames:
        save_dir = Path("test_output")
        save_dir.mkdir(exist_ok=True)

        with open(save_dir / "encoded_frame.h264", "wb") as f:
            f.write(encoded_frames[0][0])

        logger.info(f"第一帧已保存到 {save_dir / 'encoded_frame.h264'}")

    logger.info("视频编码测试完成")
    return len(encoded_frames) > 0


def run_all_tests():
    """运行所有测试"""
    tests = [
        ("屏幕捕获", test_screen_capture),
        ("ROI检测", test_roi_detection),
        ("视频编码", test_video_encoding)
    ]

    results = []

    for name, test_func in tests:
        logger.info(f"\n开始测试: {name}")
        try:
            success = test_func()
            results.append((name, success))
            logger.info(f"测试 {name}: {'通过' if success else '失败'}")
        except Exception as e:
            logger.error(f"测试 {name} 出错: {e}", exc_info=True)
            results.append((name, False))

    # 打印总结
    logger.info("\n======= 测试结果汇总 =======")
    all_passed = True
    for name, success in results:
        logger.info(f"{name}: {'通过' if success else '失败'}")
        if not success:
            all_passed = False

    if all_passed:
        logger.info("所有测试通过！")
    else:
        logger.warning("有测试失败，请检查日志。")


if __name__ == "__main__":
    run_all_tests()