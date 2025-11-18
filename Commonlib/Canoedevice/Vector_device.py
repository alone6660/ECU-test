import can
import threading
import time
from Commonlib.logger.logger import setup_logging

logger = setup_logging()

import can
import logging



def format_message_data(data):
    """将bytearray数据格式化为16进制字符串"""
    if isinstance(data, bytearray):
        hex_list = [f'0x{byte:02X}' for byte in data]
        return f"[{', '.join(hex_list)}]"
    elif isinstance(data, bytes):
        hex_list = [f'0x{byte:02X}' for byte in data]
        return f"[{', '.join(hex_list)}]"
    else:
        return str(data)

def tx_rc_checksum_cal(a_dlc, data, rc_byte, rc_start_bit, rc_len, cs_byte, rc_right_flag=True,
                             cs_right_flag=True):
    """
    计算CAN数据的滚动计数和校验和

    参数:
    a_dlc: 数据长度
    data: 数据列表 (byte数组)
    rc_byte: 滚动计数所在的字节索引
    rc_start_bit: RC最高bit位
    rc_len: RC长度，向低位横展
    cs_byte: 校验和所在的字节索引
    rc_right_flag: 是否启用滚动计数 (默认True)
    cs_right_flag: 是否启用校验和 (默认True)

    返回:
    修改后的data列表
    """
    rolling_count = 0
    checksum = 0

    # 提取RollingCount（向低位横展）
    mask = (1 << rc_len) - 1
    shift_amount = rc_start_bit - rc_len + 1
    rolling_count = (data[rc_byte] >> shift_amount) & mask

    # 递增或清零逻辑
    if rc_right_flag:
        if rolling_count < ((1 << rc_len) - 1):
            rolling_count += 1
        else:
            rolling_count = 0
    else:
        rolling_count = 0

    logger.debug(f"rc = {rolling_count}")

    # 清零RC位
    clear_mask = ~(mask << shift_amount) & 0xFF
    data[rc_byte] &= clear_mask

    # 写入新的RollingCount
    data[rc_byte] |= (rolling_count << shift_amount) & (mask << shift_amount)


    # 校验和计算
    checksum = 0
    for idx in range(a_dlc):
        if idx != cs_byte:
            checksum = (checksum + data[idx]) & 0xFF
    logger.debug(f"cr = {checksum}")
    # 写入校验和
    if cs_right_flag:
        data[cs_byte] = checksum & 0xFF
    else:
        data[cs_byte] = 0x00

    return data

class Vector:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self, interface='vector', channel=0, bitrate=500000, app_name="pythoncan"):
        if not self._initialized:
            self.interface = interface
            self.channel = channel
            self.bitrate = bitrate
            self.app_name = app_name
            self.controller = None
            self.receiving = False
            self.receive_thread = None
            self.periodic_messages = {}
            self.dynamic_data = {}  # 存储message_id对应的原始数据
            self._initialized = True

    def connect(self):
        """建立CAN总线连接"""
        if self.controller:
            logger.info("pythoncan已连接")
            return True

        try:
            self.controller = can.Bus(
                interface=self.interface,
                channel=self.channel,
                bitrate=self.bitrate,
                app_name=self.app_name
            )
            logger.info("pythoncan已连接")
            return True
        except can.CanError as e:
            logger.info(f"pythoncan连接错误: {e}")
            return False

    def send_message_with_rc_checksum(self, arbitration_id, data, rc_byte, rc_start_bit, rc_len, cs_byte,
                                      is_extended_id=False, is_fd=False):
        """发送包含RollingCount和CheckSum的报文"""


        if not self.controller:
            logger.info("未建立CAN连接")
            return False

        try:
            # 应用RollingCount和CheckSum计算
            processed_data = tx_rc_checksum_cal(
                a_dlc=len(data),
                data=data.copy(),
                rc_byte=rc_byte,
                rc_start_bit=rc_start_bit,
                rc_len=rc_len,
                cs_byte=cs_byte
            )

            message = can.Message(
                arbitration_id=arbitration_id,
                data=processed_data,
                is_extended_id=is_extended_id,
                is_fd=is_fd
            )

            self.controller.send(message, timeout=1)
            self.dynamic_data[arbitration_id] = processed_data
            logger.info(f"消息发送成功: ID=0x{message.arbitration_id:X}, 数据={format_message_data(message.data)}")
            return True
        except can.CanError as e:
            logger.info(f"CAN发送错误: {e}")
            return False


    def start_periodic_send_with_validation(self, message_id, data, period, rc_byte, rc_start_bit, rc_len, cs_byte,
                                            is_fd=False):
        """启动包含RollingCount和CheckSum验证的周期性发送"""


        def periodic_task():
            while message_id in self.periodic_messages:
                if message_id in self.dynamic_data.keys():
                    data = self.dynamic_data[message_id]
                # 每次发送都重新计算RollingCount和CheckSum

                self.send_message_with_rc_checksum(
                    message_id, data, rc_byte, rc_start_bit, rc_len, cs_byte, is_fd=is_fd
                )
                time.sleep(period-0.0005)


        if message_id in self.periodic_messages:
            logger.info(f"报文ID 0x{message_id:X} 已在周期性发送中")
            return False
        # 存储原始数据
        self.dynamic_data[message_id] = data.copy()

        self.periodic_messages[message_id] = {
            'thread': threading.Thread(target=periodic_task, daemon=True),
            'period': period,
            'rc_byte': rc_byte,
            'rc_start_bit': rc_start_bit,
            'rc_len': rc_len,
            'cs_byte': cs_byte
        }
        self.periodic_messages[message_id]['thread'].start()
        logger.info(f"启动周期性发送: ID=0x{message_id:X}, 周期={period}s")
        return True


    def send_single_message(self, arbitration_id, data, is_extended_id=False, is_fd=False):
        """发送单条CAN/CAN FD报文"""


        if not self.controller:
            logger.info("未建立CAN连接")
            return False

        try:
            message = can.Message(
                arbitration_id=arbitration_id,
                data=data,
                is_extended_id=is_extended_id,
                is_fd=is_fd
            )
            self.controller.send(message, timeout=1)
            logger.info(f"消息发送成功: ID=0x{message.arbitration_id:X}, 数据={format_message_data(message.data)}, FD={is_fd}")
            return True
        except can.CanError as e:
            logger.info(f"CAN发送错误: {e}")
            return False


    def start_periodic_send(self, message_id, data, period, is_fd=False):
        """启动周期性报文发送"""


        def periodic_task():
            while message_id in self.periodic_messages:
                self.send_single_message(message_id, data, is_fd=is_fd)
                time.sleep(period-0.0005)

        if message_id in self.periodic_messages:
            logger.info(f"报文ID 0x{message_id:X} 已在周期性发送中")
            return False

        self.periodic_messages[message_id] = {
            'thread': threading.Thread(target=periodic_task, daemon=True),
            'period': period
        }
        self.periodic_messages[message_id]['thread'].start()
        logger.info(f"启动周期性发送: ID=0x{message_id:X}, 周期={period}s, FD={is_fd}")
        return True


    def stop_periodic_send(self, message_id):
        """停止指定ID的周期性发送"""


        if message_id in self.periodic_messages:
            del self.periodic_messages[message_id]
            logger.info(f"停止周期性发送: ID=0x{message_id:X}")
            return True
        return False

    def stop_periodic_send_all(self, message_id):
        """停止所有ID的周期性发送"""
        for msg_id in list(self.periodic_messages.keys()):
            self.stop_periodic_send(msg_id)
        logger.info(f"停止所有报文周期性发送")
        return True

    def message_receiver(self):
        """报文接收线程函数"""


        while self.receiving:
            try:
                received_msg = self.controller.recv(timeout=1.0)
                if received_msg:
                    fd_status = "CAN FD" if received_msg.is_fd else "CAN"
                    logger.info(f"收到{fd_status}消息: ID=0x{received_msg.arbitration_id:X}, 数据={format_message_data(received_msg.data)}")
            except can.CanError as e:
                if self.receiving:
                    print(f"接收错误: {e}")


    def start_receive_thread(self):
        """启动报文接收线程"""


        if not self.controller:
            print("未建立CAN连接")
            return False

        self.receiving = True
        self.receive_thread = threading.Thread(target=self.message_receiver, daemon=True)
        self.receive_thread.start()
        print("启动报文接收线程")
        return True


    def stop_receive_thread(self):
        """停止报文接收线程"""


        self.receiving = False
        if self.receive_thread:
            self.receive_thread.join(timeout=2.0)
        print("停止报文接收线程")


    def shutdown(self):
        """关闭所有连接和线程"""


        self.stop_receive_thread()

        for msg_id in list(self.periodic_messages.keys()):
            self.stop_periodic_send(msg_id)

        if self.controller:
            self.controller.shutdown()
            self.controller = None
            print("CAN连接已关闭")


    @classmethod
    def get_instance(cls):
        """获取单例实例"""


        return cls._instance


    @classmethod
    def destroy_instance(cls):
        """销毁单例实例（用于测试或重新初始化）"""


        with cls._lock:
            if cls._instance:
                cls._instance.shutdown()
                cls._instance = None

if __name__ == '__main__':
    can_manager = Vector()
    if can_manager.connect():
        can_manager.start_receive_thread()

        # data = [0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]
        # can_manager.send_message_with_rc_checksum(
        #     arbitration_id=0x100,
        #     data=data,
        #     rc_byte=1,
        #     rc_start_bit=7,
        #     rc_len=4,
        #     cs_byte=7
        # )
        #
        # can_manager.start_periodic_send_with_validation(
        #     message_id=0x1b9,
        #     data=[0x11, 0x22, 0x33, 0x44, 0x55, 0x66, 0x77, 0x88],
        #     period=0.01,
        #     rc_byte=0,
        #     rc_start_bit=7,
        #     rc_len=2,
        #     cs_byte=7
        # )
        # can_manager.start_periodic_send_with_validation(
        #     message_id=0x123,
        #     data=[0x11, 0x22, 0x33, 0x44, 0x55, 0x66, 0x77, 0x88],
        #     period=0.01,
        #     rc_byte=0,
        #     rc_start_bit=7,
        #     rc_len=2,
        #     cs_byte=7
        # )
        time.sleep(2)
        can_manager.stop_periodic_send(message_id=0x1b9)
        time.sleep(10)
        can_manager.shutdown()
