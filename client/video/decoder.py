import av
import numpy as np

class VideoDecoder:
    def __init__(self):
        self.codec = av.CodecContext.create('h264', 'r')

    def decode(self, encoded_bytes: bytes):
        try:
            packet = av.packet.Packet(encoded_bytes)
            frames = self.codec.decode(packet)
            for frame in frames:
                img = frame.to_ndarray(format='bgr24')
                return img  # 只返回第一帧
        except Exception as e:
            print(f"[VideoDecoder] 解码失败: {e}")
            return None 