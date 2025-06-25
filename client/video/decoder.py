import av
import numpy as np
import logging

logger = logging.getLogger(__name__)


class VideoDecoder:
    def __init__(self):
        self.codec = av.CodecContext.create('h264', 'r')
        self.first_frame_received = False
        self.sps_pps_received = False
        self.codec_configured = False

    def decode(self, encoded_bytes: bytes):
        try:
            # 检查帧类型（SPS/PPS检测）
            if len(encoded_bytes) > 5:
                nal_type = encoded_bytes[4] & 0x1F
                if nal_type in [7, 8]:  # 7=SPS, 8=PPS
                    logger.info(f"收到SPS/PPS数据: {len(encoded_bytes)} 字节, NAL类型: {nal_type}")
                    self.sps_pps_received = True

            # 创建数据包
            packet = av.packet.Packet(encoded_bytes)

            # 尝试解码
            frames = self.codec.decode(packet)

            # 如果没有返回帧但没有抛出异常，可能是SPS/PPS信息
            if not frames:
                return None

            # 处理解码后的帧
            for frame in frames:
                img = frame.to_ndarray(format='bgr24')
                if not self.first_frame_received:
                    logger.info(f"首帧解码成功: {img.shape}")
                    self.first_frame_received = True
                    self.codec_configured = True
                return img  # 只返回第一帧

        except Exception as e:
            logger.error(f"解码失败: {e}")
            # 如果是第一帧，记录更详细的错误
            if not self.first_frame_received:
                import traceback
                logger.error(f"首帧解码失败详情: {traceback.format_exc()}")
            return None