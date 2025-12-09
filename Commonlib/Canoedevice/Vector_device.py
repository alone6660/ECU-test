# -*- coding: utf-8 -*-
import sys
import os
import traceback

# 添加项目根目录到Python路径
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(project_root)
import threading
import time
from logger.logger import setup_logging
logger = setup_logging()
logger.setLevel("DEBUG")
import can


def format_message_data(data):
    """将bytearray数据格式化为16进制字符串"""
    if isinstance(data, (bytearray, bytes)):
        hex_list = [f'0x{byte:02X}' for byte in data]
        return f"[{', '.join(hex_list)}]"
    return str(data)


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
            self.receive_callbacks = []  # 存储消息接收回调函数
            self._initialized = True

    def connect(self):
        """连接CAN控制器"""
        if self.controller:
            logger.info("CAN控制器已连接")
            return True

        try:
            logger.info(f"正在连接Vector CAN设备: interface={self.interface}, channel={self.channel}, bitrate={self.bitrate}")
            
            # 创建CAN总线连接
            self.controller = can.Bus(
                interface=self.interface,
                channel=self.channel,
                bitrate=self.bitrate,
                app_name=self.app_name
            )
            
            logger.info(f"CAN控制器连接成功! 控制器类型: {type(self.controller)}")
            return True
        except can.CanError as e:
            logger.error(f"CAN控制器连接失败: {e}")
            return False
        except Exception as e:
            logger.error(f"连接过程中发生未知错误: {e}")
            return False
            
    def _create_message(self, arbitration_id, data, is_extended_id=False, is_fd=False):
        """创建CAN消息的内部方法"""
        # 确保消息ID是整数
        arbitration_id = int(arbitration_id)
        
        # 确保数据是字节数组
        if isinstance(data, str):
            # 从十六进制字符串解析数据
            data = data.replace(' ', '').replace('0x', '')
            if len(data) % 2 != 0:
                data = '0' + data
            data = bytearray.fromhex(data)
        elif not isinstance(data, (bytearray, bytes)):
            data = bytearray(data)
        
        # 自动判断是否需要扩展ID
        if not is_extended_id and arbitration_id >= 0x800:
            is_extended_id = True
        
        return can.Message(
            arbitration_id=arbitration_id,
            data=data,
            is_extended_id=is_extended_id,
            is_fd=is_fd
        )
    
    def send_message(self, arbitration_id, data, is_extended_id=False, is_fd=False):
        """发送CAN/CAN FD消息"""
        if not self.controller:
            logger.error("未连接CAN控制器")
            return False

        try:
            processed_data = data.copy() if hasattr(data, 'copy') else data
            
            # 创建消息
            message = self._create_message(arbitration_id, processed_data, is_extended_id, is_fd)
            
            # 发送消息
            self.controller.send(message, timeout=1)
            self.dynamic_data[arbitration_id] = processed_data
            logger.info(f"消息发送成功: ID=0x{message.arbitration_id:X}, 数据={format_message_data(message.data)}")
            return True
        except can.CanError as e:
            logger.error(f"CAN发送错误: {e}")
            return False
        except Exception as e:
            logger.error(f"发送消息时发生未知错误: {e}")
            return False
            
    def start_periodic_send(self, message_id, data, period, is_fd=False):
        """启动周期性发送任务
        
        Args:
            message_id: 消息ID
            data: 消息数据 (16进制字符串或bytearray)
            period: 发送周期 (秒)
            is_fd: 是否为CAN FD消息
            
        Returns:
            bool: 启动结果
        """
        try:
            message_id = int(message_id)
            logger.debug(f"开始启动周期性发送: ID=0x{message_id:X}, period={period}s")
            
            # 检查控制器连接
            if not self.controller:
                logger.error(f"无法启动周期性发送: 控制器未连接, ID=0x{message_id:X}")
                return False
                
            # 停止已有相同ID的周期性发送
            if message_id in self.periodic_messages:
                logger.debug(f"ID=0x{message_id:X}已存在，停止原有周期性发送")
                self.stop_periodic_send(message_id)
            
            # 解析周期
            if isinstance(period, str):
                period = float(period)
            
            # 处理数据格式
            if isinstance(data, str):
                data = bytearray.fromhex(data.replace(" ", ""))
            elif not isinstance(data, (bytearray, bytes)):
                logger.error(f"周期性发送数据格式错误, ID=0x{message_id:X}")
                return False
            
            # 存储数据
            self.dynamic_data[message_id] = data.copy()
            logger.debug(f"存储dynamic_data: ID=0x{message_id:X}, data={format_message_data(data)}")
            
            # 创建停止事件
            stop_event = threading.Event()
            
            # 创建并启动线程
            thread = threading.Thread(
                target=self.periodic_task,
                args=(message_id, stop_event, period, is_fd),
                daemon=True
            )
            thread.start()
            logger.debug(f"线程已启动: ID=0x{message_id:X}, 线程名={thread.name}")
            
            # 记录任务信息
            self.periodic_messages[message_id] = {
                'thread': thread,
                'stop_event': stop_event,
                'period': period,
                'is_fd': is_fd
            }
            
            logger.info(f"开始周期性发送: ID=0x{message_id:X}, 数据={format_message_data(data)}, 周期={period}s")
            return True
        except Exception as e:
            logger.error(f"启动周期性发送失败, ID=0x{message_id:X}, 错误: {e}")
            logger.debug(f"错误堆栈: {traceback.format_exc()}")
            return False
    
    def periodic_task(self, message_id, stop_event, period, is_fd=False):
        """周期性发送任务函数"""
        logger.debug(f"periodic_task 开始执行: ID=0x{message_id:X}, 周期={period}s")
        
        # 使用更高精度的时间函数
        start_time = time.perf_counter()
        iteration_count = 0
        
        # 定义最小睡眠阈值（Windows上time.sleep的精度通常约为15ms）
        MIN_SLEEP_DURATION = 0.001  # 1ms
        
        while not stop_event.is_set():
            try:
                iteration_count += 1
                # 计算下一次发送的绝对时间
                next_send_time = start_time + (iteration_count * period)
                
                logger.debug(f"periodic_task 循环: ID=0x{message_id:X}, 当前时间={time.perf_counter():.6f}, 下次发送时间={next_send_time:.6f}")
                
                if not self.controller:
                    logger.error(f"周期性任务停止: 控制器已断开, ID=0x{message_id:X}")
                    break
                    
                if message_id not in self.periodic_messages:
                    logger.error(f"周期性任务停止: 消息ID不在周期性列表中, ID=0x{message_id:X}")
                    logger.debug(f"当前periodic_messages: {list(self.periodic_messages.keys())}")
                    break
                
                # 获取当前数据副本
                if message_id not in self.dynamic_data:
                    logger.error(f"周期性任务停止: 消息ID不在动态数据中, ID=0x{message_id:X}")
                    logger.debug(f"当前dynamic_data: {list(self.dynamic_data.keys())}")
                    break
                    
                current_data = self.dynamic_data[message_id].copy()
                logger.debug(f"获取当前数据: ID=0x{message_id:X}, 数据={format_message_data(current_data)}")
                
                # 记录消息发送开始时间
                send_start_time = time.perf_counter()
                
                # 发送消息
                logger.debug(f"准备发送周期性消息: ID=0x{message_id:X}, 数据={format_message_data(current_data)}")
                result = self.send_message(message_id, current_data, is_fd=is_fd)
                logger.debug(f"发送结果: ID=0x{message_id:X}, 结果={result}")
                if not result:
                    logger.error(f"周期性消息发送失败: ID=0x{message_id:X}")
                
                # 记录消息发送结束时间
                send_end_time = time.perf_counter()
                send_duration = send_end_time - send_start_time
                logger.debug(f"消息发送耗时: ID=0x{message_id:X}, 耗时={send_duration:.6f}s")
                
            except Exception as e:
                logger.error(f"周期性任务执行错误, ID=0x{message_id:X}, 错误: {e}")
                logger.debug(f"错误堆栈: {traceback.format_exc()}")
            finally:
                # 计算需要等待的时间
                current_time = time.perf_counter()
                sleep_duration = next_send_time - current_time
                logger.debug(f"计算睡眠时长: ID=0x{message_id:X}, 下次发送时间={next_send_time:.6f}, 当前时间={current_time:.6f}, 睡眠时长={sleep_duration:.6f}s")
                
                if sleep_duration > 0:
                    # 如果剩余时间足够长，使用time.sleep
                    if sleep_duration > MIN_SLEEP_DURATION:
                        # 只睡眠大部分时间，留一小部分时间进行微调
                        time.sleep(sleep_duration - MIN_SLEEP_DURATION)
                    
                    # 使用忙等待来微调剩余时间，确保精确到达目标时间
                    while time.perf_counter() < next_send_time:
                        # 忙等待，直到接近目标时间
                        pass
                else:
                    # 如果已经超过了计划发送时间，记录延迟警告
                    logger.warning(f"周期性发送延迟: ID=0x{message_id:X}, 延迟时间={abs(sleep_duration):.6f}s")
                    # 调整start_time以避免进一步的累积延迟
                    start_time = current_time - (iteration_count * period)
    
    def add_receive_callback(self, callback):
        """添加接收消息的回调函数"""
        if callable(callback) and callback not in self.receive_callbacks:
            self.receive_callbacks.append(callback)
    
    def stop_periodic_send(self, message_id):
        """停止指定ID的周期性发送"""
        message_id = int(message_id)
        
        if message_id in self.periodic_messages:
            # 停止周期性发送任务
            task_info = self.periodic_messages[message_id]
            if 'stop_event' in task_info:
                task_info['stop_event'].set()
            
            del self.periodic_messages[message_id]
            
            # 从dynamic_data中移除
            if message_id in self.dynamic_data:
                del self.dynamic_data[message_id]
                
            logger.info(f"停止周期性发送: ID=0x{message_id:X}")
            return True
        return False

    def stop_periodic_send_all(self):
        """停止所有周期性发送"""
        for msg_id in list(self.periodic_messages.keys()):
            self.stop_periodic_send(msg_id)
        logger.info(f"停止所有周期性发送")
        return True

    def message_receiver(self):
        """消息接收线程函数"""
        while self.receiving:
            try:
                received_msg = self.controller.recv(timeout=1.0)
                if received_msg:
                    fd_status = "CAN FD" if received_msg.is_fd else "CAN"
                    
                    logger.info(f"收到{fd_status}消息: ID=0x{received_msg.arbitration_id:X}, 数据={format_message_data(received_msg.data)}")
                    
                    # 调用所有注册的回调函数，只传递原始消息
                    for callback in self.receive_callbacks:
                        try:
                            callback(received_msg)
                        except Exception as e:
                            logger.error(f"执行接收回调函数时出错: {e}")
            except can.CanError as e:
                if self.receiving:
                    logger.error(f"接收错误: {e}")

    def start_receive_thread(self):
        """启动消息接收线程"""
        if not self.controller:
            logger.error("未连接CAN控制器")
            return False

        self.receiving = True
        self.receive_thread = threading.Thread(target=self.message_receiver, daemon=True)
        self.receive_thread.start()
        logger.info("启动消息接收线程")
        return True

    def stop_receive_thread(self):
        """停止消息接收线程"""
        self.receiving = False
        if self.receive_thread:
            self.receive_thread.join(timeout=2.0)
        logger.info("停止消息接收线程")

    def shutdown(self):
        """关闭所有资源和线程，彻底清理并断开控制器连接"""
        logger.info("正在关闭所有资源...")
        
        # 停止接收线程
        try:
            self.stop_receive_thread()
        except Exception as e:
            logger.error(f"停止接收线程失败: {e}")

        # 停止所有周期性发送
        try:
            periodic_msg_ids = list(self.periodic_messages.keys())
            for msg_id in periodic_msg_ids:
                self.stop_periodic_send(msg_id)
        except Exception as e:
            logger.error(f"停止周期性发送失败: {e}")

        # 断开控制器连接
        try:
            if self.controller:
                logger.info("正在断开CAN控制器连接...")
                self.controller.shutdown()
                self.controller = None
                logger.info("CAN控制器断开连接成功")
        except Exception as e:
            logger.error(f"断开CAN控制器连接失败: {e}")
            self.controller = None

        # 清理动态数据
        self.dynamic_data.clear()
        
        logger.info("所有资源已成功关闭")

    @classmethod
    def get_instance(cls):
        """获取单例实例"""
        return cls._instance

    @classmethod
    def destroy_instance(cls):
        """销毁单例实例并释放内部资源以便下次重新初始化"""
        with cls._lock:
            if cls._instance:
                cls._instance.shutdown()
                cls._instance = None

if __name__ == '__main__':
    try:
        print("=== Vector_device 类方法调用示例 ===")
        
        # 1. 创建实例
        can_manager = Vector()
        print("1. 创建Vector实例成功")
        
        # 2. 连接CAN控制器
        if can_manager.connect():
            print("2. CAN控制器连接成功")
            
            # 3. 发送单条报文
            result = can_manager.send_message(0x100, "01234567")
            print(f"3. 发送单条报文结果: {result}")
            
            # 4. 定义接收回调函数
            def receive_callback(message):
                print(f"   收到报文: ID=0x{message.arbitration_id:X}, 数据={format_message_data(message.data)}")
            
            # 5. 添加接收回调
            can_manager.add_receive_callback(receive_callback)
            print("5. 添加接收回调成功")
            
            # # 6. 启动接收线程
            # result = can_manager.start_receive_thread()
            # print(f"6. 启动接收线程结果: {result}")
            
            # 7. 启动周期性发送
            result = can_manager.start_periodic_send(0x200, "89ABCDEF", 0.01)
            print(f"7. 启动周期性发送(0x200)结果: {result}")
            
            # 8. 再启动一个周期性发送
            result = can_manager.start_periodic_send(0x300, "00FF00FF", 0.02)
            print(f"8. 启动周期性发送(0x300)结果: {result}")
            
            # 等待一段时间，观察发送和接收
            print("\n等待5秒，观察报文发送...")
            time.sleep(500)
            
            # 9. 停止特定周期性发送
            result = can_manager.stop_periodic_send(0x200)
            print(f"9. 停止周期性发送(0x200)结果: {result}")
            
            # 等待一段时间
            print("\n等待3秒...")
            time.sleep(300)
            
            # 10. 停止所有周期性发送
            result = can_manager.stop_periodic_send_all()
            print(f"10. 停止所有周期性发送结果: {result}")
            #
            # # 11. 停止接收线程
            # can_manager.stop_receive_thread()
            # print("11. 停止接收线程成功")
            
            # 类方法示例
            print("\n=== 类方法调用示例 ===")
            
            # 12. 获取单例实例
            instance = Vector.get_instance()
            print(f"12. 获取单例实例: {instance}")
            
            # 13. 关闭控制器
            can_manager.shutdown()
            print("13. 关闭控制器成功")
            
            # 14. 销毁单例实例
            Vector.destroy_instance()
            print("14. 销毁单例实例成功")
        else:
            print("2. CAN控制器连接失败")
            
    except Exception as e:
        print(f"程序执行出错: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print("=== 所有方法调用示例完成 ===")
