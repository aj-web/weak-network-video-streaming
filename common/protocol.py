"""
通信协议定义
定义客户端和服务端之间的消息格式和通信规则
"""

import json
import struct
import time
from typing import Dict, Any, Tuple, Optional, Union, List

from common.constants import PROTOCOL_VERSION, MessageType


class ProtocolError(Exception):
    """协议错误异常"""
    pass


class VideoStreamProtocol:
    """
    视频流通信协议
    负责消息的序列化、反序列化和验证
    """

    @staticmethod
    def create_video_packet(
            frame_data: bytes,
            frame_id: int,
            timestamp: Optional[int] = None,
            is_keyframe: bool = False,
            width: int = 0,
            height: int = 0,
            sequence_number: int = 0,
            total_fragments: int = 1,
            fragment_index: int = 0
    ) -> bytes:
        """
        创建视频数据包

        Args:
            frame_data: 编码后的视频帧数据
            frame_id: 帧ID
            timestamp: 时间戳(毫秒)，如果为None则使用当前时间
            is_keyframe: 是否是关键帧
            width: 视频宽度
            height: 视频高度
            sequence_number: 帧内的序列号
            total_fragments: 该帧的总分片数
            fragment_index: 当前分片索引

        Returns:
            打包后的视频数据包
        """
        if timestamp is None:
            timestamp = int(time.time() * 1000)  # 毫秒时间戳

        # 创建数据包头部
        header = {
            "type": MessageType.VIDEO_DATA,
            "version": PROTOCOL_VERSION,
            "frame_id": frame_id,
            "timestamp": timestamp,
            "is_keyframe": is_keyframe,
            "width": width,
            "height": height,
            "data_size": len(frame_data),
            "sequence_number": sequence_number,
            "total_fragments": total_fragments,
            "fragment_index": fragment_index
        }

        # 序列化头部
        header_json = json.dumps(header).encode('utf-8')

        # 创建包含头部长度的数据包
        header_len = len(header_json)
        packet = struct.pack('!I', header_len) + header_json + frame_data

        return packet

    @staticmethod
    def parse_packet(data: bytes) -> Tuple[Dict[str, Any], bytes]:
        """
        解析数据包

        Args:
            data: 原始数据包

        Returns:
            (头部字典, 负载数据)的元组

        Raises:
            ProtocolError: 解析错误时
        """
        # 数据包应该至少包含头部长度字段(4字节)
        if len(data) < 4:
            raise ProtocolError("数据包太短")

        # 解析头部长度
        header_len = struct.unpack('!I', data[:4])[0]

        # 检查数据包是否包含完整头部
        if len(data) < 4 + header_len:
            raise ProtocolError("数据包不完整")

        # 解析头部
        try:
            header_json = data[4:4 + header_len]
            header = json.loads(header_json.decode('utf-8'))
        except json.JSONDecodeError:
            raise ProtocolError("头部JSON解析失败")
        except UnicodeDecodeError:
            raise ProtocolError("头部编码错误")

        # 提取负载
        payload = data[4 + header_len:]

        # 验证类型字段
        if "type" not in header:
            raise ProtocolError("头部缺少类型字段")

        # 验证版本
        if header.get("version") != PROTOCOL_VERSION:
            raise ProtocolError(f"协议版本不匹配: {header.get('version')} != {PROTOCOL_VERSION}")

        return header, payload

    @staticmethod
    def create_network_status(
            rtt: float,
            packet_loss: float,
            bandwidth: float,
            timestamp: Optional[int] = None,
            client_id: str = ""
    ) -> bytes:
        """
        创建网络状态消息

        Args:
            rtt: 往返时间(毫秒)
            packet_loss: 丢包率(百分比)
            bandwidth: 带宽(bps)
            timestamp: 时间戳(毫秒)
            client_id: 客户端ID

        Returns:
            序列化的网络状态消息
        """
        if timestamp is None:
            timestamp = int(time.time() * 1000)

        message = {
            "type": MessageType.NETWORK_STATUS,
            "version": PROTOCOL_VERSION,
            "timestamp": timestamp,
            "client_id": client_id,
            "rtt": rtt,
            "packet_loss": packet_loss,
            "bandwidth": bandwidth
        }

        return json.dumps(message).encode('utf-8')

    @staticmethod
    def create_config_message(config: Dict[str, Any]) -> bytes:
        """
        创建配置消息

        Args:
            config: 配置参数字典

        Returns:
            序列化的配置消息
        """
        message = {
            "type": MessageType.CONFIG,
            "version": PROTOCOL_VERSION,
            "timestamp": int(time.time() * 1000),
            "config": config
        }

        return json.dumps(message).encode('utf-8')

    @staticmethod
    def create_ack_message(
            message_id: str,
            status: bool = True,
            info: Optional[Dict[str, Any]] = None
    ) -> bytes:
        """
        创建确认消息

        Args:
            message_id: 被确认的消息ID
            status: 确认状态(True=成功, False=失败)
            info: 附加信息

        Returns:
            序列化的确认消息
        """
        message = {
            "type": MessageType.ACK,
            "version": PROTOCOL_VERSION,
            "timestamp": int(time.time() * 1000),
            "message_id": message_id,
            "status": status
        }

        if info:
            message["info"] = info

        return json.dumps(message).encode('utf-8')

    @staticmethod
    def create_error_message(
            error_code: int,
            error_message: str,
            details: Optional[Dict[str, Any]] = None
    ) -> bytes:
        """
        创建错误消息

        Args:
            error_code: 错误代码
            error_message: 错误描述
            details: 错误详情

        Returns:
            序列化的错误消息
        """
        message = {
            "type": MessageType.ERROR,
            "version": PROTOCOL_VERSION,
            "timestamp": int(time.time() * 1000),
            "error_code": error_code,
            "error_message": error_message
        }

        if details:
            message["details"] = details

        return json.dumps(message).encode('utf-8')