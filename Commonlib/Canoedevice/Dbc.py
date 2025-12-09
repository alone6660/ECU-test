# -*- coding: utf-8 -*-
# 标准库导入
import json
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum

# 第三方库导入
import cantools

# 本地导入


# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)





@dataclass
class SignalInfo:
    """信号信息数据类"""
    name: str
    start_bit: int
    length: int
    byte_order: str
    scale: float
    offset: float
    minimum: Optional[float]
    maximum: Optional[float]
    unit: Optional[str]
    is_signed: bool
    comment: Optional[str] = None
    value_descriptions: Optional[Dict[int, str]] = None

@dataclass
class MessageInfo:
    """消息信息数据类"""
    name: str
    frame_id: int
    length: int
    cycle_time: Optional[int]
    senders: List[str]
    receivers: List[str]
    signals: List[str]
    comment: Optional[str] = None
    is_fd: bool = False


class CANDatabase:
    """
    CAN数据库封装类，提供方便的DBC文件操作接口
    支持DBC解析、报文编解码、信号验证等功能
    """

    def __init__(self, dbc_file_path: str):
        """
        初始化CAN数据库

        Args:
            dbc_file_path: DBC文件路径
        """
        self.dbc_file_path = dbc_file_path
        self.db = None
        self._load_database()

    def _load_database(self):
        """加载DBC数据库文件"""
        try:
            self.db = cantools.database.load_file(self.dbc_file_path)
            logger.info(f"成功加载DBC文件: {self.dbc_file_path}")
            logger.info(f"数据库包含 {len(self.db.messages)} 条消息")
        except Exception as e:
            logger.error(f"加载DBC文件失败: {e}")
            raise





    def get_database_summary(self) -> Dict[str, Any]:
        """
        获取数据库摘要信息

        Returns:
            数据库摘要字典
        """
        try:
            return {
                'dbc_file': self.dbc_file_path,
                'message_count': len(self.db.messages),
                'signal_count': sum(len(msg.signals) for msg in self.db.messages),
                'sender_count': len(self.get_all_senders()),
                'receiver_count': len(self.get_all_receivers()),
                'version': self.db.version if hasattr(self.db, 'version') else 'unknown'
            }
        except Exception as e:
            logger.error(f"获取数据库摘要失败: {e}")
            return {}

    def get_all_messages(self) -> List[Dict[str, Any]]:
        """
        获取所有消息信息

        Returns:
            消息信息列表
        """
        if not self.db:
            return []

        messages_info = []
        for msg in self.db.messages:
            message_info = {
                'name': msg.name,
                'frame_id': msg.frame_id,
                'length': msg.length,
                'cycle_time': msg.cycle_time,
                'senders': msg.senders if hasattr(msg, 'senders') else [],
                'comment': msg.comment if hasattr(msg, 'comment') else None,
                'signals': []
            }

            for signal in msg.signals:
                signal_info = {
                    'name': signal.name,
                    'start': signal.start,
                    'length': signal.length,
                    'byte_order': signal.byte_order,
                    'scale': signal.scale,
                    'offset': signal.offset,
                    'minimum': signal.minimum,
                    'maximum': signal.maximum,
                    'unit': signal.unit,
                    'is_signed': signal.is_signed,
                    'comment': signal.comment if hasattr(signal, 'comment') else None
                }
                message_info['signals'].append(signal_info)

            messages_info.append(message_info)

        return messages_info

    def get_message_by_name(self, message_name: str) -> Optional[MessageInfo]:
        """
        通过消息名称获取消息信息

        Args:
            message_name: 消息名称

        Returns:
            消息信息对象
        """
        try:
            msg = self.db.get_message_by_name(message_name)
            return MessageInfo(
                name=msg.name,
                frame_id=msg.frame_id,
                length=msg.length,
                cycle_time=msg.cycle_time,
                senders=msg.senders if hasattr(msg, 'senders') else [],
                receivers=[],  # 初始化为空列表，因为cantools可能不提供接收者信息
                signals=[signal.name for signal in msg.signals],
                comment=msg.comment if hasattr(msg, 'comment') else None,
                is_fd=False  # 默认非FD消息
            )
        except KeyError:
            logger.error(f"未找到消息: {message_name}")
            return None

    def get_signal_by_name(self, message_name: str, signal_name: str) -> Optional[SignalInfo]:
        """
        通过消息名称和信号名称获取信号信息

        Args:
            message_name: 消息名称
            signal_name: 信号名称

        Returns:
            信号信息对象
        """
        try:
            msg = self.db.get_message_by_name(message_name)
            signal = msg.get_signal_by_name(signal_name)

            return SignalInfo(
                name=signal.name,
                start_bit=signal.start if hasattr(signal, 'start') else signal.start_bit if hasattr(signal, 'start_bit') else 0,
                length=signal.length,
                byte_order=signal.byte_order,
                scale=signal.scale,
                offset=signal.offset,
                minimum=signal.minimum,
                maximum=signal.maximum,
                unit=signal.unit,
                is_signed=signal.is_signed,
                comment=signal.comment if hasattr(signal, 'comment') else None
            )
        except (KeyError, AttributeError):
            logger.error(f"未找到信号: {message_name}.{signal_name}")
            return None
            
    def get_message_by_id(self, frame_id: int) -> Optional[MessageInfo]:
        """
        根据帧ID获取消息信息

        Args:
            frame_id: 消息的帧ID

        Returns:
            消息信息，如果未找到则返回None
        """
        try:
            msg = self.db.get_message_by_frame_id(frame_id)
            return MessageInfo(
                name=msg.name,
                frame_id=msg.frame_id,
                length=msg.length,
                cycle_time=msg.cycle_time,
                senders=msg.senders,
                receivers=msg.receivers if hasattr(msg, 'receivers') else [],
                signals=[signal.name for signal in msg.signals],
                comment=msg.comment,
                is_fd=msg.is_fd if hasattr(msg, 'is_fd') else False
            )
        except Exception as e:
            logger.error(f"根据帧ID获取消息失败: {e}")
            return None
    
    def get_message_name_by_id(self, frame_id: int) -> Optional[str]:
        """
        根据帧ID获取消息名称

        Args:
            frame_id: 消息的帧ID

        Returns:
            消息名称，如果未找到则返回None
        """
        msg_info = self.get_message_by_id(frame_id)
        return msg_info.name if msg_info else None
    
    def get_signal_info(self, message_name: str, signal_name: str) -> Optional[SignalInfo]:
        """
        获取信号的详细信息

        Args:
            message_name: 消息名称
            signal_name: 信号名称

        Returns:
            信号信息，如果未找到则返回None
        """
        try:
            msg = self.db.get_message_by_name(message_name)
            signal = msg.get_signal_by_name(signal_name)
            
            return SignalInfo(
                name=signal.name,
                start_bit=signal.start_bit if hasattr(signal, 'start_bit') else 0,
                length=signal.length,
                byte_order=ByteOrder.LITTLE_ENDIAN if signal.byte_order == 'little_endian' else ByteOrder.BIG_ENDIAN,
                scale=signal.scale,
                offset=signal.offset,
                minimum=signal.minimum if hasattr(signal, 'minimum') else None,
                maximum=signal.maximum if hasattr(signal, 'maximum') else None,
                unit=signal.unit,
                comment=signal.comment,
                value_descriptions=signal.value_descriptions if hasattr(signal, 'value_descriptions') else None
            )
        except Exception as e:
            logger.error(f"获取信号信息失败: {e}")
            return None
    
    def get_message_signals(self, message_name: str) -> List[SignalInfo]:
        """
        获取消息的所有信号信息

        Args:
            message_name: 消息名称

        Returns:
            信号信息列表，如果消息未找到则返回空列表
        """
        try:
            msg = self.db.get_message_by_name(message_name)
            signals = []
            for signal in msg.signals:
                signals.append(SignalInfo(
                    name=signal.name,
                    start_bit=signal.start_bit if hasattr(signal, 'start_bit') else 0,
                    length=signal.length,
                    byte_order=ByteOrder.LITTLE_ENDIAN if signal.byte_order == 'little_endian' else ByteOrder.BIG_ENDIAN,
                    scale=signal.scale,
                    offset=signal.offset,
                    minimum=signal.minimum if hasattr(signal, 'minimum') else None,
                    maximum=signal.maximum if hasattr(signal, 'maximum') else None,
                    unit=signal.unit,
                    comment=signal.comment,
                    value_descriptions=signal.value_descriptions if hasattr(signal, 'value_descriptions') else None
                ))
            return signals
        except Exception as e:
            logger.error(f"获取消息信号失败: {e}")
            return []
    
    def get_all_senders(self) -> List[str]:
        """
        获取DBC文件中所有的发送节点

        Returns:
            发送节点列表
        """
        try:
            senders = set()
            for msg in self.db.messages:
                if msg.senders:
                    senders.update(msg.senders)
            return sorted(list(senders))
        except Exception as e:
            logger.error(f"获取所有发送节点失败: {e}")
            return []
    
    def get_all_receivers(self) -> List[str]:
        """
        获取DBC文件中所有的接收节点

        Returns:
            接收节点列表
        """
        try:
            receivers = set()
            for msg in self.db.messages:
                if hasattr(msg, 'receivers') and msg.receivers:
                    receivers.update(msg.receivers)
            return sorted(list(receivers))
        except Exception as e:
            logger.error(f"获取所有接收节点失败: {e}")
            return []
    
    def find_messages_by_signal(self, signal_name: str) -> List[str]:
        """
        根据信号名称查找包含该信号的所有消息

        Args:
            signal_name: 信号名称

        Returns:
            包含该信号的消息名称列表
        """
        try:
            messages = []
            for msg in self.db.messages:
                for signal in msg.signals:
                    if signal.name == signal_name:
                        messages.append(msg.name)
                        break
            return messages
        except Exception as e:
            logger.error(f"根据信号查找消息失败: {e}")
            return []

    def encode_message(self, message_name: str, signal_values: Dict[str, float], use_defaults: bool = True, validate: bool = True) -> Optional[bytes]:
        """
        编码CAN消息

        Args:
            message_name: 消息名称
            signal_values: 信号值字典
            use_defaults: 是否使用默认值填充未提供的信号
            validate: 是否验证信号值在有效范围内

        Returns:
            编码后的CAN数据
        """
        try:
            msg = self.db.get_message_by_name(message_name)
            if not msg:
                logger.error(f"未找到消息: {message_name}")
                return None

            # 创建完整的信号值字典
            full_signal_values = {}
            
            for signal in msg.signals:
                signal_name = signal.name
                
                # 如果提供了信号值，使用提供的值
                if signal_name in signal_values:
                    value = signal_values[signal_name]
                    
                    # 验证信号值
                    if validate:
                        # 检查是否在有效范围内
                        has_min = hasattr(signal, 'minimum') and signal.minimum is not None
                        has_max = hasattr(signal, 'maximum') and signal.maximum is not None
                        
                        if has_min and has_max and not (signal.minimum <= value <= signal.maximum):
                            logger.warning(f"信号 {signal_name} 的值 {value} 超出范围 [{signal.minimum}, {signal.maximum}]，将被截断")
                            value = max(signal.minimum, min(signal.maximum, value))
                    
                    full_signal_values[signal_name] = value
                
                # 如果未提供且使用默认值
                elif use_defaults:
                    # 尝试使用信号的最小值作为默认值，如果没有则使用0
                    default_value = signal.minimum if hasattr(signal, 'minimum') and signal.minimum is not None else 0.0
                    full_signal_values[signal_name] = default_value
                
                # 如果未提供且不使用默认值
                else:
                    logger.error(f"未提供信号 {signal_name} 的值")
                    return None

            data = msg.encode(full_signal_values)
            logger.info(f"成功编码消息 {message_name}，数据: {data.hex()}")
            return data
        except Exception as e:
            logger.error(f"编码消息失败: {e}")
            return None

    def decode_message(self, message_name: str, data: bytes) -> Optional[Dict[str, float]]:
        """
        解码CAN消息

        Args:
            message_name: 消息名称
            data: CAN数据

        Returns:
            解码后的信号值字典
        """
        try:
            msg = self.db.get_message_by_name(message_name)
            return msg.decode(data)
        except Exception as e:
            logger.error(f"解码消息失败: {e}")
            return None
    def get_message_cycle_time(self, message_name: str) -> Optional[int]:
        """
        获取消息循环时间

        Args:
            message_name: 消息名称

        Returns:
            循环时间(毫秒)
        """
        try:
            msg = self.db.get_message_by_name(message_name)
            return msg.cycle_time
        except KeyError:
            logger.error(f"未找到消息: {message_name}")
            return None



    def save_messages_to_json(self, output_file: str) -> bool:
        """
        将数据库消息保存为JSON文件

        Args:
            output_file: 输出文件路径

        Returns:
            保存是否成功
        """
        try:
            messages_data = self.get_all_messages()
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(messages_data, f, indent=2, ensure_ascii=False)
            logger.info(f"消息数据已保存到: {output_file}")
            return True
        except Exception as e:
            logger.error(f"保存JSON文件失败: {e}")
            return False

    def save_message_to_json(self, message_identifiers: List[Any], output_file: str = "messages_info.json") -> bool:
        """
        将指定的一个或多个报文的属性及信号输出到同一个JSON文件
        只包含必要的报文信息、信号及其默认值和周期

        Args:
            message_identifiers: 要保存的报文标识符列表，可以是报文名称（str）或CAN ID（int/hex）
            output_file: 输出文件路径，默认为messages_info.json

        Returns:
            是否保存成功
        """
        try:
            # 获取所有消息
            all_messages = self.get_all_messages()
            
            # 收集所有指定的消息并格式化
            formatted_messages = []
            for identifier in message_identifiers:
                # 查找指定的消息
                target_message = None
                
                # 根据报文名称或CAN ID查找
                for msg in all_messages:
                    if isinstance(identifier, str) and msg['name'] == identifier:
                        target_message = msg
                        break
                    elif isinstance(identifier, (int, float)) and msg['frame_id'] == identifier:
                        target_message = msg
                        break
                
                if not target_message:
                    logger.error(f"未找到指定报文: {identifier}")
                    continue
                
                # 格式化报文信息，将frame_id转换为16进制格式
                formatted_msg = {
                    'name': target_message['name'],
                    'frame_id': f"0x{target_message['frame_id']:X}",  # 转换为16进制字符串
                    'length': target_message['length'],
                    'cycle_time': target_message['cycle_time'],
                    'signals': []
                }
                
                # 格式化信号信息，只保留名称和默认值
                for signal in target_message['signals']:
                    # 计算默认值（使用最小值或0）
                    default_value = str(signal['minimum'] if signal['minimum'] is not None else 0.0)
                    
                    formatted_signal = {
                        'name': signal['name'],
                        'default_value': default_value
                    }
                    formatted_msg['signals'].append(formatted_signal)
                
                formatted_messages.append(formatted_msg)
            
            if not formatted_messages:
                logger.error("没有找到任何指定的报文")
                return False
            
            # 保存到单个JSON文件
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(formatted_messages, f, indent=2, ensure_ascii=False)
            logger.info(f"所有指定报文数据已保存到: {output_file}")
            
            return True
        except Exception as e:
            logger.error(f"保存指定报文到JSON文件失败: {e}")
            return False

    def validate_signal_value(self, message_name: str, signal_name: str, value: float) -> bool:
        """
        验证信号值是否在有效范围内

        Args:
            message_name: 消息名称
            signal_name: 信号名称
            value: 信号值

        Returns:
            是否有效
        """
        signal_info = self.get_signal_by_name(message_name, signal_name)
        if not signal_info:
            return False

        if signal_info.minimum is not None and value < signal_info.minimum:
            return False

        if signal_info.maximum is not None and value > signal_info.maximum:
            return False

        return True

    def get_messages_by_cycle_time(self, min_cycle: int = 0, max_cycle: int = 10000) -> List[Dict[str, Any]]:
        """
        根据循环时间筛选消息

        Args:
            min_cycle: 最小循环时间
            max_cycle: 最大循环时间

        Returns:
            符合条件的消息列表
        """
        filtered_messages = []
        for msg_info in self.get_all_messages():
            cycle_time = msg_info.get('cycle_time')
            if cycle_time is not None and min_cycle <= cycle_time <= max_cycle:
                filtered_messages.append(msg_info)

        return filtered_messages


if __name__ == '__main__':
    """DBC数据库操作示例"""
    import os
    
    # 注意：当前目录下有一个dbc_341_1b9_1d2_120_53d_config.json文件，但它不是标准的DBC文件
    # 标准DBC文件通常有.dbc扩展名
    # 使用原始字符串格式（在前面加上r）来避免反斜杠被解释为转义字符
    # 请替换为您实际的DBC文件路径
    dbc_file_path = r"E:\workspace\01_ABS\03_N001\Files\SGMW_N001_ABS_20250919_V1.0.dbc"
    

    # 1. 创建CANDatabase实例
    dbc_db = CANDatabase(dbc_file_path)

    # 6. 将指定报文的属性及信号输出到JSON文件
    print(f"\n=== 保存指定报文到JSON文件 ===")
    # 使用第一个消息作为示例

    # 保存指定CAN ID的报文
    target_message_ids = [0X341, 0X1B9]
    print(f"正在保存报文 {target_message_ids}")
    if dbc_db.save_message_to_json(target_message_ids):
        print(f"[OK] 成功保存报文 {target_message_ids}")
    else:
        print(f"[ERROR] 保存报文 {target_message_ids} 失败")
        
