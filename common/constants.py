"""
共享常量定义
包含服务端和客户端共用的常量值
"""

# 协议版本
PROTOCOL_VERSION = "1.0"

# 默认网络参数
DEFAULT_PORT = 4433
DEFAULT_FPS = 30
DEFAULT_BITRATE = 3000000  # 3 Mbps

# 视频参数限制
MIN_BITRATE = 500000    # 500 Kbps
MAX_BITRATE = 10000000  # 10 Mbps
MIN_FPS = 10
MAX_FPS = 60

# 消息类型
class MessageType:
    VIDEO_DATA = "video_data"
    NETWORK_STATUS = "network_status"
    CONFIG = "config"
    ACK = "ack"
    ERROR = "error"

# 视频帧类型
class FrameType:
    KEYFRAME = "keyframe"
    DELTAFRAME = "deltaframe"

# 网络状态级别
class NetworkQuality:
    EXCELLENT = "excellent"  # RTT < 50ms, 丢包率 < 0.5%
    GOOD = "good"            # RTT < 100ms, 丢包率 < 1%
    FAIR = "fair"            # RTT < 200ms, 丢包率 < 2%
    POOR = "poor"            # RTT < 300ms, 丢包率 < 5%
    BAD = "bad"              # RTT >= 300ms 或 丢包率 >= 5%

# ROI相关常量
DEFAULT_ROI_SIZE = 200  # 默认ROI区域大小(像素)