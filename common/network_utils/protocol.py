# common/network_utils/protocol.py

import struct
import zlib
import time
import random

# 包类型定义
PACKET_TYPE_VIDEO = 0
PACKET_TYPE_AUDIO = 1
PACKET_TYPE_CONTROL = 2
PACKET_TYPE_FEC = 3
PACKET_TYPE_HEARTBEAT = 4

class Packet:
    """网络数据包基类"""
    
    # 包头格式: type(1B) + seq(4B) + timestamp(8B) + flags(1B) + size(4B)
    HEADER_SIZE = 18
    HEADER_FORMAT = "!BIQBI"
    
    def __init__(self, packet_type, seq_num, timestamp=None, flags=0, payload=None):
        self.packet_type = packet_type
        self.seq_num = seq_num
        self.timestamp = timestamp if timestamp is not None else time.time()
        self.flags = flags
        self.payload = payload if payload is not None else b''

    def serialize(self):
        """将数据包序列化为字节"""
        # 将浮点时间戳转换为整数时间戳(毫秒)
        int_timestamp = int(self.timestamp * 1000)

        header = struct.pack(
            self.HEADER_FORMAT,
            self.packet_type,
            self.seq_num,
            int_timestamp,  # 使用整数时间戳
            self.flags,
            len(self.payload)
        )
        return header + self.payload
    
    @classmethod
    def deserialize(cls, data):
        """从字节反序列化为数据包"""
        if len(data) < cls.HEADER_SIZE:
            return None
            
        header = data[:cls.HEADER_SIZE]
        packet_type, seq_num, timestamp, flags, payload_size = struct.unpack(
            cls.HEADER_FORMAT, header
        )
        
        if len(data) < cls.HEADER_SIZE + payload_size:
            return None
            
        payload = data[cls.HEADER_SIZE:cls.HEADER_SIZE + payload_size]
        
        # 将整数时间戳转换回浮点时间戳
        float_timestamp = timestamp / 1000.0
        
        # 根据类型创建具体的包对象
        if packet_type == PACKET_TYPE_VIDEO:
            return VideoPacket.from_base(
                cls(packet_type, seq_num, float_timestamp, flags, payload)
            )
        elif packet_type == PACKET_TYPE_CONTROL:
            return ControlPacket.from_base(
                cls(packet_type, seq_num, float_timestamp, flags, payload)
            )
        elif packet_type == PACKET_TYPE_FEC:
            return FECPacket.from_base(
                cls(packet_type, seq_num, float_timestamp, flags, payload)
            )
        elif packet_type == PACKET_TYPE_HEARTBEAT:
            return HeartbeatPacket.from_base(
                cls(packet_type, seq_num, float_timestamp, flags, payload)
            )
        else:
            return cls(packet_type, seq_num, float_timestamp, flags, payload)
    
    def __repr__(self):
        return f"Packet(type={self.packet_type}, seq={self.seq_num}, size={len(self.payload)})"


class VideoPacket(Packet):
    """视频数据包"""
    
    # 视频包标志位
    FLAG_KEYFRAME = 0x01
    FLAG_ROI = 0x02
    FLAG_FRAGMENT = 0x04  # 表示这是一个分片
    FLAG_FRAGMENT_END = 0x08  # 表示这是最后一个分片
    
    def __init__(self, seq_num, timestamp=None, flags=0, payload=None, 
                 frame_index=0, fragment_index=0, total_fragments=1):
        super().__init__(PACKET_TYPE_VIDEO, seq_num, timestamp, flags, payload)
        
        # 视频特有属性
        self.frame_index = frame_index
        self.fragment_index = fragment_index
        self.total_fragments = total_fragments
        
        # 包头后，添加视频特有头部: frame_index(4B) + fragment_index(2B) + total_fragments(2B)
        # 这部分将加入到payload前
        self.video_header = struct.pack("!IHH", frame_index, fragment_index, total_fragments)
        
    def serialize(self):
        """将视频包序列化为字节"""
        # 将视频头部添加到有效载荷前
        combined_payload = self.video_header + self.payload
        
        # 将浮点时间戳转换为整数时间戳(毫秒)
        int_timestamp = int(self.timestamp * 1000)
        
        # 使用基类的序列化，但传入组合后的有效载荷
        header = struct.pack(
            self.HEADER_FORMAT,
            self.packet_type,
            self.seq_num,
            int_timestamp,
            self.flags,
            len(combined_payload)
        )
        return header + combined_payload
    
    @classmethod
    def from_base(cls, base_packet):
        """从基本包创建视频包"""
        if len(base_packet.payload) < 8:  # 至少需要视频头部大小
            return None
            
        # 解析视频头部
        video_header = base_packet.payload[:8]
        frame_index, fragment_index, total_fragments = struct.unpack("!IHH", video_header)
        
        # 提取实际视频数据
        video_payload = base_packet.payload[8:]
        
        # 创建视频包
        return cls(
            base_packet.seq_num,
            base_packet.timestamp,
            base_packet.flags,
            video_payload,
            frame_index,
            fragment_index,
            total_fragments
        )
    
    def is_keyframe(self):
        """是否是关键帧"""
        return bool(self.flags & self.FLAG_KEYFRAME)
    
    def is_roi(self):
        """是否包含ROI数据"""
        return bool(self.flags & self.FLAG_ROI)
    
    def is_fragment(self):
        """是否是分片"""
        return bool(self.flags & self.FLAG_FRAGMENT)
    
    def is_last_fragment(self):
        """是否是最后一个分片"""
        return bool(self.flags & self.FLAG_FRAGMENT_END)
    
    def __repr__(self):
        flags_str = []
        if self.is_keyframe():
            flags_str.append("KEY")
        if self.is_roi():
            flags_str.append("ROI")
        if self.is_fragment():
            flags_str.append(f"FRAG({self.fragment_index}/{self.total_fragments})")
            
        return f"VideoPacket(seq={self.seq_num}, frame={self.frame_index}, " \
               f"flags=[{', '.join(flags_str)}], size={len(self.payload)})"


class ControlPacket(Packet):
    """控制数据包"""
    
    # 控制包类型
    CTRL_TYPE_ACK = 0
    CTRL_TYPE_NACK = 1
    CTRL_TYPE_STATS = 2
    CTRL_TYPE_CONFIG = 3
    
    def __init__(self, seq_num, ctrl_type, ctrl_data=None, timestamp=None):
        super().__init__(PACKET_TYPE_CONTROL, seq_num, timestamp, 0, None)
        
        self.ctrl_type = ctrl_type
        self.ctrl_data = ctrl_data if ctrl_data is not None else {}
        
        # 序列化控制数据
        import json
        self.payload = json.dumps(self.ctrl_data).encode()
    
    @classmethod
    def from_base(cls, base_packet):
        """从基本包创建控制包"""
        # 解析控制类型(payload的第一个字节)
        if not base_packet.payload:
            return None
            
        ctrl_type = base_packet.payload[0]
        
        # 解析控制数据
        import json
        try:
            ctrl_data = json.loads(base_packet.payload[1:].decode())
        except:
            ctrl_data = {}
        
        # 创建控制包
        return cls(base_packet.seq_num, ctrl_type, ctrl_data, base_packet.timestamp)
    
    def __repr__(self):
        ctrl_types = {
            self.CTRL_TYPE_ACK: "ACK",
            self.CTRL_TYPE_NACK: "NACK",
            self.CTRL_TYPE_STATS: "STATS",
            self.CTRL_TYPE_CONFIG: "CONFIG"
        }
        ctrl_type_str = ctrl_types.get(self.ctrl_type, f"UNKNOWN({self.ctrl_type})")
        return f"ControlPacket(seq={self.seq_num}, type={ctrl_type_str})"


class FECPacket(Packet):
    """前向纠错数据包"""
    
    def __init__(self, seq_num, block_index, timestamp=None, 
                 source_packets=None, fec_data=None):
        super().__init__(PACKET_TYPE_FEC, seq_num, timestamp, 0, None)
        
        self.block_index = block_index
        self.source_packets = source_packets if source_packets is not None else []
        
        # 如果提供了源包，计算FEC数据
        if source_packets and fec_data is None:
            self.fec_data = self._compute_fec(source_packets)
        else:
            self.fec_data = fec_data if fec_data is not None else b''
        
        # FEC头部: block_index(4B) + num_source_packets(2B) + source_packet_seq_nums(可变)
        source_seq_nums = b''.join(struct.pack("!I", p.seq_num) for p in self.source_packets)
        self.fec_header = struct.pack("!IH", block_index, len(self.source_packets)) + source_seq_nums
        
        # 组合头部和数据
        self.payload = self.fec_header + self.fec_data
    
    @classmethod
    def from_base(cls, base_packet):
        """从基本包创建FEC包"""
        if len(base_packet.payload) < 6:  # 至少需要FEC头部基本大小
            return None
            
        # 解析FEC头部
        block_index, num_source_packets = struct.unpack("!IH", base_packet.payload[:6])
        
        # 解析源包序号
        source_seq_nums = []
        for i in range(num_source_packets):
            offset = 6 + i * 4
            if offset + 4 > len(base_packet.payload):
                break
            seq_num, = struct.unpack("!I", base_packet.payload[offset:offset+4])
            source_seq_nums.append(seq_num)
        
        # 提取FEC数据
        data_offset = 6 + num_source_packets * 4
        fec_data = base_packet.payload[data_offset:] if data_offset < len(base_packet.payload) else b''
        
        # 创建FEC包(临时)
        fec_packet = cls(base_packet.seq_num, block_index, base_packet.timestamp, None, fec_data)
        
        # 保存源包序号，以便后续重建
        fec_packet.source_seq_nums = source_seq_nums
        
        return fec_packet
    
    def _compute_fec(self, packets):
        """计算FEC数据(简化版本)"""
        # 简单版本: 对所有包的有效载荷进行XOR运算
        # 注意: 真实FEC应使用更复杂的纠删码如Reed-Solomon
        if not packets:
            return b''
            
        # 找出最大有效载荷大小
        max_size = max(len(p.payload) for p in packets)
        
        # 初始化FEC数据为0
        fec_data = bytearray(max_size)
        
        # 对所有包进行XOR
        for packet in packets:
            for i in range(len(packet.payload)):
                fec_data[i] ^= packet.payload[i]
        
        return bytes(fec_data)
    
    def __repr__(self):
        return f"FECPacket(seq={self.seq_num}, block={self.block_index}, " \
               f"sources={len(self.source_packets)}, size={len(self.fec_data)})"


class HeartbeatPacket(Packet):
    """心跳包，用于检测网络状态"""
    
    def __init__(self, seq_num, timestamp=None, client_stats=None):
        """
        初始化心跳包
        
        Args:
            seq_num: 序列号
            timestamp: 时间戳（可选）
            client_stats: 客户端统计信息（可选）
        """
        super().__init__(PACKET_TYPE_HEARTBEAT, seq_num, timestamp, 0, None)
        
        # 心跳包携带客户端网络统计信息
        self.client_stats = client_stats if client_stats is not None else {}
        
        # 序列化统计数据
        import json
        self.payload = json.dumps(self.client_stats).encode()
    
    @classmethod
    def from_base(cls, base_packet):
        """从基本包创建心跳包"""
        # 解析统计数据
        import json
        try:
            client_stats = json.loads(base_packet.payload.decode())
        except:
            client_stats = {}
        
        # 创建心跳包
        return cls(base_packet.seq_num, base_packet.timestamp, client_stats)
    
    def __repr__(self):
        return f"HeartbeatPacket(seq={self.seq_num}, timestamp={self.timestamp:.3f})"
    


# 实现分片工具，用于处理大帧
def fragment_video_frame(frame_data, frame_index, timestamp, is_keyframe, 
                          max_payload_size=1400, seq_start=0):
    """
    将一个视频帧分片为多个数据包
    
    Args:
        frame_data: 帧数据(字节)
        frame_index: 帧索引
        timestamp: 时间戳
        is_keyframe: 是否是关键帧
        max_payload_size: 每个分片最大有效载荷大小
        seq_start: 起始序列号
        
    Returns:
        分片包列表
    """
    # 确保参数类型正确
    frame_index = int(frame_index)
    seq_start = int(seq_start)
    max_payload_size = int(max_payload_size)
    
    # 确保timestamp是浮点数
    if isinstance(timestamp, int):
        timestamp = float(timestamp)
    
    fragments = []
    total_size = len(frame_data)
    total_fragments = (total_size + max_payload_size - 1) // max_payload_size
    
    for i in range(total_fragments):
        # 计算分片范围
        start = i * max_payload_size
        end = min(start + max_payload_size, total_size)
        
        # 设置标志
        flags = 0
        if is_keyframe:
            flags |= VideoPacket.FLAG_KEYFRAME
        
        if total_fragments > 1:
            flags |= VideoPacket.FLAG_FRAGMENT
            if i == total_fragments - 1:
                flags |= VideoPacket.FLAG_FRAGMENT_END
        
        # 创建分片包
        fragment = VideoPacket(
            seq_num=seq_start + i,
            timestamp=timestamp,
            flags=flags,
            payload=frame_data[start:end],
            frame_index=frame_index,
            fragment_index=i,
            total_fragments=total_fragments
        )
        
        fragments.append(fragment)
    
    return fragments


def reassemble_video_frame(fragments):
    """
    从分片重组视频帧
    
    Args:
        fragments: 分片包列表
        
    Returns:
        重组后的帧数据，如果分片不完整则返回None
    """
    if not fragments:
        return None
    
    # 检查分片是否完整
    total_fragments = fragments[0].total_fragments
    if len(fragments) != total_fragments:
        return None
    
    # 按分片索引排序
    fragments.sort(key=lambda x: x.fragment_index)
    
    # 检查是否有缺失的分片
    for i, fragment in enumerate(fragments):
        if fragment.fragment_index != i:
            return None
    
    # 重组帧数据
    frame_data = b''.join(fragment.payload for fragment in fragments)
    
    return {
        "data": frame_data,
        "timestamp": fragments[0].timestamp,
        "frame_index": fragments[0].frame_index,
        "is_keyframe": fragments[0].is_keyframe()
    }