# common/utils.py

import time
import os
import sys
import logging
import numpy as np
import cv2

# 配置日志
def setup_logger(name, log_file=None, level=logging.INFO):
    """
    设置日志记录器
    
    Args:
        name: 日志记录器名称
        log_file: 日志文件路径
        level: 日志级别
        
    Returns:
        日志记录器实例
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # 创建格式化器
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # 创建控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # 如果指定了日志文件，创建文件处理器
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    return logger

# 性能测量装饰器
def timing(f):
    """
    测量函数执行时间的装饰器
    
    Args:
        f: 要测量的函数
        
    Returns:
        包装后的函数
    """
    def wrap(*args, **kwargs):
        time_start = time.time()
        ret = f(*args, **kwargs)
        time_end = time.time()
        print(f"{f.__name__} took {time_end - time_start:.4f} sec")
        return ret
    return wrap

# 图像处理工具
def resize_image(image, width=None, height=None):
    """
    调整图像大小，保持宽高比
    
    Args:
        image: 输入图像
        width: 目标宽度，None表示按height等比例缩放
        height: 目标高度，None表示按width等比例缩放
        
    Returns:
        调整后的图像
    """
    if width is None and height is None:
        return image
    
    h, w = image.shape[:2]
    
    if width is None:
        # 按height等比例缩放
        ratio = height / float(h)
        dim = (int(w * ratio), height)
    elif height is None:
        # 按width等比例缩放
        ratio = width / float(w)
        dim = (width, int(h * ratio))
    else:
        # 指定宽高
        dim = (width, height)
    
    # 调整大小
    resized = cv2.resize(image, dim, interpolation=cv2.INTER_AREA)
    return resized

# 网络工具
def is_port_in_use(port, host='localhost'):
    """
    检查端口是否被占用
    
    Args:
        port: 端口号
        host: 主机名
        
    Returns:
        端口是否被占用
    """
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.connect((host, port))
        s.shutdown(socket.SHUT_RDWR)
        return True
    except:
        return False
    finally:
        s.close()

def get_available_port(start_port=8000, max_tries=100):
    """
    获取可用端口
    
    Args:
        start_port: 起始端口号
        max_tries: 最大尝试次数
        
    Returns:
        可用端口号，如果没有找到则返回None
    """
    for port in range(start_port, start_port + max_tries):
        if not is_port_in_use(port):
            return port
    return None