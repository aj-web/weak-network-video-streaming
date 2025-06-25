import av
import numpy as np
import logging

logger = logging.getLogger(__name__)


class VideoDecoder:
    def __init__(self):
        self.codec = av.CodecContext.create('h264', 'r')
        self.first_frame_received = False
        self.sps_pps_received = False
        self.sps_pps_data = None  # 存储SPS/PPS数据
        self.codec_configured = False
        self.pending_frames = []  # 存储在接收到SPS/PPS之前的帧

    def decode(self, encoded_bytes: bytes, frame_info=None):
        try:
            # 检查是否是参数集（SPS/PPS）
            is_parameter_sets = frame_info and frame_info.get('type') == 'parameter_sets'

            # 检查帧类型（SPS/PPS检测）
            if len(encoded_bytes) > 5:
                nal_type = encoded_bytes[4] & 0x1F
                if nal_type in [7, 8]:  # 7=SPS, 8=PPS
                    logger.info(f"收到SPS/PPS数据: {len(encoded_bytes)} 字节, NAL类型: {nal_type}")
                    self.sps_pps_received = True
                    self.sps_pps_data = encoded_bytes

                    # 将SPS/PPS数据发送给解码器
                    self._send_packet_to_decoder(encoded_bytes)

                    # 处理之前积累的帧
                    if self.pending_frames:
                        logger.info(f"处理 {len(self.pending_frames)} 个挂起的帧")
                        results = []
                        for frame_data in self.pending_frames:
                            result = self._send_packet_to_decoder(frame_data)
                            if result is not None:
                                results.append(result)
                        self.pending_frames = []
                        if results:
                            return results[0]  # 返回第一个成功解码的帧
                    return None

            # 如果尚未收到SPS/PPS，将帧添加到待处理列表
            if not self.sps_pps_received:
                logger.debug(f"尚未收到SPS/PPS，将帧添加到待处理列表: {len(encoded_bytes)} 字节")
                self.pending_frames.append(encoded_bytes)
                return None

            # 已收到SPS/PPS，正常解码
            return self._send_packet_to_decoder(encoded_bytes)

        except Exception as e:
            logger.error(f"解码失败: {e}")
            # 如果是第一帧，记录更详细的错误
            if not self.first_frame_received:
                import traceback
                logger.error(f"首帧解码失败详情: {traceback.format_exc()}")
            return None

    def _send_packet_to_decoder(self, encoded_bytes):
        """向解码器发送数据包并处理结果"""
        packet = av.packet.Packet(encoded_bytes)
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

        return None