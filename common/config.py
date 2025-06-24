# common/config.py

class Config:
    """系统全局配置"""
    
    # 视频相关配置
    VIDEO_WIDTH = 1280
    VIDEO_HEIGHT = 720
    TARGET_FPS = 30
    
    # 编码配置
    class EncodingProfiles:
        HIGH_QUALITY = {
            "codec": "h264",  # 也可以使用"h265"，但兼容性更好
            "resolution": (1280, 720),
            "fps": 30,
            "bitrate": 5000000,  # 5 Mbps
            "gop": 30,
            "preset": "veryfast",
            "tune": "zerolatency"
        }
        
        BALANCED = {
            "codec": "h264",
            "resolution": (960, 540),
            "fps": 30,
            "bitrate": 2500000,  # 2.5 Mbps
            "gop": 30,
            "preset": "ultrafast",
            "tune": "zerolatency"
        }
        
        LOW_BANDWIDTH = {
            "codec": "h264",
            "resolution": (640, 360),
            "fps": 20,
            "bitrate": 1000000,  # 1 Mbps
            "gop": 20,
            "preset": "ultrafast",
            "tune": "zerolatency"
        }
        
        EMERGENCY = {
            "codec": "h264",
            "resolution": (480, 270),
            "fps": 10,
            "bitrate": 500000,  # 0.5 Mbps
            "gop": 10,
            "preset": "ultrafast",
            "tune": "zerolatency"
        }
    
    # 网络相关配置
    PACKET_SIZE = 1200  # 默认数据包大小
    MAX_PACKET_SIZE = 1400
    MIN_PACKET_SIZE = 500
    
    # FEC配置
    FEC_OVERHEAD_DEFAULT = 0.2  # 默认20%的FEC开销
    FEC_MIN_OVERHEAD = 0.05
    FEC_MAX_OVERHEAD = 0.5
    
    # 网络状态阈值
    NETWORK_THRESHOLDS = {
        "good": {
            "rtt": 100,         # ms
            "packet_loss": 0.01  # 1%
        },
        "medium": {
            "rtt": 200,
            "packet_loss": 0.02
        },
        "poor": {
            "rtt": 300,
            "packet_loss": 0.05
        }
    }
    
    # ROI编码配置
    ROI_PRIORITY_LEVELS = 5  # 区域优先级等级数
    ROI_MAX_QP_DELTA = 10    # 最大QP差异
    ROI_MOUSE_RADIUS = 200   # 鼠标周围ROI区域半径(像素)
    
    # 服务器配置
    SERVER_PORT = 8000
    
    # 客户端配置
    CLIENT_BUFFER_SIZE = 5  # 帧缓冲数量
    
    # 调试配置
    DEBUG_MODE = True
    SAVE_STATS = True
    STATS_INTERVAL = 1.0  # 秒