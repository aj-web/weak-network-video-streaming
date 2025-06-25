#!/usr/bin/env python3
"""
简单的视频编码器测试脚本
"""

import numpy as np
import time
from server.video_encoder import VideoEncoder

def test_basic_encoding():
    """测试基本编码功能"""
    print("开始测试基本编码功能...")
    
    # 创建编码器
    encoder = VideoEncoder(
        width=640, 
        height=480, 
        fps=30, 
        bitrate=2000000,
        roi_qp_offset=-8
    )
    
    try:
        # 启动编码器
        encoder.start()
        print("编码器已启动")
        
        # 创建测试帧
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        # 添加一些颜色
        frame[100:200, 100:200, 0] = 255  # 红色方块
        frame[200:300, 300:400, 1] = 255  # 绿色方块
        
        # 测试无ROI编码
        print("测试无ROI编码...")
        success = encoder.encode_frame(frame)
        print(f"无ROI编码结果: {success}")
        
        # 等待编码完成
        time.sleep(0.1)
        
        # 测试ROI编码
        print("测试ROI编码...")
        roi_info = {
            'x': 100,
            'y': 100,
            'width': 200,
            'height': 200,
            'importance': 1.0
        }
        success = encoder.encode_frame(frame, roi_info)
        print(f"ROI编码结果: {success}")
        
        # 等待编码完成
        time.sleep(0.1)
        
        # 测试不同重要性的ROI
        print("测试不同重要性的ROI...")
        roi_info_high = {
            'x': 300,
            'y': 300,
            'width': 100,
            'height': 100,
            'importance': 1.5
        }
        success = encoder.encode_frame(frame, roi_info_high)
        print(f"高重要性ROI编码结果: {success}")
        
        # 等待编码完成
        time.sleep(0.1)
        
        # 获取当前设置
        settings = encoder.get_current_settings()
        print(f"当前编码设置: {settings}")
        
        print("基本编码测试完成")
        
    except Exception as e:
        print(f"测试过程中出现错误: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # 停止编码器
        encoder.stop()
        print("编码器已停止")

def test_parameter_validation():
    """测试参数验证"""
    print("\n开始测试参数验证...")
    
    # 测试无效参数
    invalid_params = [
        (0, 480, "宽度为0"),
        (640, -1, "高度为负数"),
        (640, 480, "帧率为0", {"fps": 0}),
        (640, 480, "帧率过大", {"fps": 121}),
        (640, 480, "码率为0", {"bitrate": 0}),
        (640, 480, "GOP为0", {"gop_size": 0}),
        (640, 480, "QP偏移过小", {"roi_qp_offset": -21}),
        (640, 480, "QP偏移过大", {"roi_qp_offset": 21}),
    ]
    
    for width, height, desc, *extra_params in invalid_params:
        try:
            if extra_params:
                encoder = VideoEncoder(width, height, **extra_params[0])
            else:
                encoder = VideoEncoder(width, height)
            print(f"❌ {desc} - 应该抛出异常但没有")
        except ValueError as e:
            print(f"✅ {desc} - 正确抛出异常: {e}")
        except Exception as e:
            print(f"❌ {desc} - 抛出意外异常: {e}")
    
    print("参数验证测试完成")

if __name__ == "__main__":
    print("=== 视频编码器测试 ===")
    
    # 测试参数验证
    test_parameter_validation()
    
    # 测试基本编码功能
    test_basic_encoding()
    
    print("\n=== 测试完成 ===") 