# -*- coding: utf-8 -*-
"""消息调度器，用于管理周期性发送任务，支持动态更新信号值、报文组装和解析、CheckSum和RollingCount计算"""

import json
import os
import threading
import time
from collections import defaultdict

from Vector_device import Vector
from logger.logger import setup_logging

logger = setup_logging()

def tx_rc_checksum_cal(a_dlc, data, rc_byte, rc_start_bit, rc_len, cs_byte, current_rc, rc_right_flag=True, cs_right_flag=True):
    """
    计算CAN数据的滚动计数器和校验值

    参数:
    a_dlc: 数据长度
    data: 数据列表 (byte数组)
    rc_byte: 滚动计数器所在的字节位置
    rc_start_bit: RC起始bit位
    rc_len: RC长度, 从低位扩展
    cs_byte: 校验值所在的字节位置
    current_rc: 当前滚动计数器值
    rc_right_flag: 是否递增滚动计数器 (默认True)
    cs_right_flag: 是否计算校验值 (默认True)

    返回:
    修改后的数据列表和新的滚动计数器值
    """
    rolling_count = current_rc
    checksum = 0

    # 更新滚动计数器逻辑
    if rc_right_flag:
        if rolling_count < ((1 << rc_len) - 1):
            rolling_count += 1
        else:
            rolling_count = 0
    else:
        rolling_count = 0

    logger.debug(f"rc = {rolling_count}")

    # 清空RC位
    mask = (1 << rc_len) - 1
    shift_amount = rc_start_bit - rc_len + 1
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
    # 写入校验值
    if cs_right_flag:
        data[cs_byte] = checksum & 0xFF
    
    return data, rolling_count


class MessageScheduler:
    """消息调度器类，用于管理周期性发送任务"""
    
    def __init__(self, vector_interface='vector', channel=0, bitrate=500000):
        """初始化消息调度器
        
        Args:
            vector_interface: Vector接口类型
            channel: 通道号
            bitrate: 波特率
        """
        self.vector = Vector(interface=vector_interface, channel=channel, bitrate=bitrate)
        self.periodic_tasks = {}  # 存储周期性任务，key为message_id
        self.task_lock = threading.Lock()
        
    def connect(self):
        """连接CAN设备
        
        Returns:
            bool: 连接成功返回True，失败返回False
        """
        return self.vector.connect()
        
    def load_dbc(self, dbc_file_path):
        """加载DBC文件
        
        Args:
            dbc_file_path: DBC文件路径
            
        Returns:
            bool: 加载成功返回True，失败返回False
        """
        try:
            from Dbc import CANDatabase
            self.dbc_database = CANDatabase(dbc_file_path)
            logger.info(f"成功加载DBC文件: {dbc_file_path}")
            return True
        except Exception as e:
            logger.error(f"加载DBC文件失败: {e}")
            self.dbc_database = None
            return False
        
    def load_config(self, json_config_path):
        """
        加载JSON配置文件，支持messages_info.json格式和旧版配置格式
        
        Args:
            json_config_path: JSON配置文件路径
            
        Returns:
            bool: 加载成功返回True，失败返回False
            
        支持的配置文件格式：
        1. messages_info.json格式（推荐）:
        [
          {
            "name": "消息名称",
            "frame_id": "0x341",
            "length": 8,
            "cycle_time": 100,
            "signals": [
              {
                "name": "信号名",
                "default_value": 值或'CNT'/'CR'
              }
            ]
          }
        ]
        
        2. 旧版配置格式（兼容）:
        {
          "initial_messages": [...],
          "periodic_messages": [...]
        }
        
        注意：
        1. 周期信息优先从DBC文件获取，DBC中没有时使用配置文件中的值
        2. 信号的default_value为'RC'时表示该信号是RollingCount
        3. 信号的default_value为'CS'时表示该信号是CheckSum
        """
        try:
            with open(json_config_path, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
            
            # 检测配置文件格式
            if isinstance(config_data, list):
                # 新格式：messages_info.json
                self.config = self._parse_messages_info_format(config_data)
            else:
                # 旧格式：兼容原有配置
                self.config = config_data
            
            logger.info(f"成功加载配置文件: {json_config_path}")
            return True
        except Exception as e:
            logger.error(f"加载配置文件失败: {e}")
            return False
    
    def _parse_messages_info_format(self, messages_data):
        """
        解析messages_info.json格式的配置文件
        
        Args:
            messages_data: 从messages_info.json加载的数据（列表格式）
            
        Returns:
            转换后的配置字典，兼容原有配置格式
        """
        config = {
            "initial_messages": [],
            "periodic_messages": []
        }
        
        for message_data in messages_data:
            message_name = message_data["name"]
            cycle_time = message_data.get("cycle_time")
            
            # 提取信号值，处理RC和CS
            signal_values = {}
            rc_signal = None
            cs_signal = None
            
            for signal in message_data["signals"]:
                signal_name = signal["name"]
                default_value = signal["default_value"]
                
                # 检查JSON配置中的默认值是否为RC或CS
                if isinstance(default_value, str):
                    default_value_str = default_value.strip().upper()
                    if default_value_str == "RC":
                        rc_signal = signal_name
                        # 设置默认值为0，后续会被自动计算的RC值替换
                        signal_values[signal_name] = 0
                    elif default_value_str == "CS":
                        cs_signal = signal_name
                        # 设置默认值为0，后续会被自动计算的CS值替换
                        signal_values[signal_name] = 0
                    else:
                        # 尝试将字符串转换为数字
                        try:
                            signal_values[signal_name] = int(default_value)
                        except ValueError:
                            try:
                                signal_values[signal_name] = float(default_value)
                            except ValueError:
                                signal_values[signal_name] = default_value
                else:
                    # 默认值已经是数字类型
                    signal_values[signal_name] = default_value
            
            # 创建消息配置
            msg_config = {
                "message_name": message_name,
                "signal_values": signal_values,
                "is_fd": False
            }
            
            # 如果有cycle_time，添加到周期消息配置
            if cycle_time is not None:
                msg_config["period"] = cycle_time / 1000.0  # 转换为秒
                msg_config["rolling_count"] = 0  # 初始化滚动计数器
                msg_config["fixed_rc"] = False  # 是否固定RollingCount
                msg_config["fixed_cs"] = False  # 是否固定CheckSum
            
            # 获取RC和CS的位置信息（需要从DBC中获取）
            if self.dbc_database:
                message_info = self.dbc_database.get_message_by_name(message_name)
                
                if message_info:
                    if rc_signal:
                        # 查找RC信号的位置信息
                        rc_info = self.dbc_database.get_signal_by_name(message_name, rc_signal)
                        if rc_info:
                            msg_config["rc_byte"] = rc_info.start_bit // 8  # 计算所在字节
                            msg_config["rc_start_bit"] = rc_info.start_bit
                            msg_config["rc_len"] = rc_info.length
                        
                    if cs_signal:
                        # 查找CS信号的位置信息
                        cs_info = self.dbc_database.get_signal_by_name(message_name, cs_signal)
                        if cs_info:
                            msg_config["cs_byte"] = cs_info.start_bit // 8  # 计算所在字节
            
            # 添加到周期性消息
            config["periodic_messages"].append(msg_config)
        
        return config
            
    def start_initial_messages(self):
        """发送初始消息"""
        if not hasattr(self, 'config') or 'initial_messages' not in self.config:
            logger.warning("配置文件中没有初始消息")
            return
            
        for msg_config in self.config['initial_messages']:
            try:
                message_name = msg_config['message_name']
                signal_values = msg_config['signal_values']
                is_fd = msg_config.get('is_fd', False)
                
                # 组装报文数据
                if self.dbc_database:
                    try:
                        # 使用DBC文件组装报文
                        arbitration_id = self.dbc_database.get_message_by_name(message_name).frame_id
                        data = self.dbc_database.encode_message(message_name, signal_values)
                        data = list(data)
                        
                        # 应用RollingCount和CheckSum计算（如果配置了相关参数）
                        if all(param is not None for param in [msg_config.get('rc_byte'), 
                                                              msg_config.get('rc_start_bit'), 
                                                              msg_config.get('rc_len'), 
                                                              msg_config.get('cs_byte')]):
                            # 调用本地实现的tx_rc_checksum_cal函数
                            data, _ = tx_rc_checksum_cal(
                                a_dlc=len(data),
                                data=data,
                                rc_byte=msg_config['rc_byte'],
                                rc_start_bit=msg_config['rc_start_bit'],
                                rc_len=msg_config['rc_len'],
                                cs_byte=msg_config['cs_byte'],
                                current_rc=0  # 初始消息使用默认的0值
                            )
                        
                        # 发送消息
                        success = self.vector.send_message(arbitration_id, data, is_fd=is_fd)
                        if success:
                            logger.info(f"成功发送初始消息: {message_name}")
                        else:
                            logger.error(f"发送初始消息失败: {message_name}")
                    except Exception as e:
                        logger.error(f"组装初始消息 {message_name} 失败: {e}")
                else:
                    logger.error("未加载DBC文件，无法发送初始消息")
            except Exception as e:
                logger.error(f"处理初始消息 {msg_config.get('message_name', '未知')} 时出错: {e}")
            time.sleep(0.01)  # 短暂延迟，避免消息冲突
            
    def start_periodic_messages(self):
        """开始发送所有周期性消息
        
        Returns:
            list: 任务ID列表
        """
        if not hasattr(self, 'config') or 'periodic_messages' not in self.config:
            logger.warning("配置文件中没有周期性消息")
            return []
            
        task_ids = []
        for msg_config in self.config['periodic_messages']:
            try:
                # 从DBC文件获取周期（单位：毫秒），如果DBC中没有则使用配置文件中的值
                if self.dbc_database:
                    cycle_time_ms = self.dbc_database.get_message_cycle_time(msg_config['message_name'])
                    if cycle_time_ms is not None:
                        period = cycle_time_ms / 1000.0  # 转换为秒
                        logger.info(f"从DBC获取消息 {msg_config['message_name']} 的周期: {period}秒")
                    else:
                        period = msg_config['period']
                        logger.warning(f"DBC中未找到消息 {msg_config['message_name']} 的周期，使用配置文件中的值: {period}秒")
                else:
                    period = msg_config['period']
                    logger.warning("未加载DBC文件，使用配置文件中的周期值")
                
                task_id = self.add_periodic_message(
                    message_name=msg_config['message_name'],
                    signal_values=msg_config['signal_values'],
                    period=period,
                    is_fd=msg_config.get('is_fd', False),
                    rc_byte=msg_config.get('rc_byte'),
                    rc_start_bit=msg_config.get('rc_start_bit'),
                    rc_len=msg_config.get('rc_len'),
                    cs_byte=msg_config.get('cs_byte')
                )
                if task_id:
                    task_ids.append(task_id)
            except Exception as e:
                logger.error(f"添加周期性消息 {msg_config.get('message_name', '未知')} 时出错: {e}")
        return task_ids
        
    def add_periodic_message(self, message_name, signal_values, period=None, is_fd=False, 
                            rc_byte=None, rc_start_bit=None, rc_len=None, cs_byte=None):
        """添加周期性消息任务
        
        Args:
            message_name: 消息名称
            signal_values: 信号值字典
            period: 发送周期（秒），如果为None则从DBC文件获取
            is_fd: 是否是CAN FD消息
            rc_byte: RollingCount所在字节（通过JSON配置）
            rc_start_bit: RC起始位（通过JSON配置）
            rc_len: RC长度（通过JSON配置）
            cs_byte: 校验和所在字节（通过JSON配置）
            
        Returns:
            int: message_id，失败返回None
        """
        # 如果未指定周期，从DBC文件获取
        if period is None and self.dbc_database:
            cycle_time_ms = self.dbc_database.get_message_cycle_time(message_name)
            if cycle_time_ms is not None:
                period = cycle_time_ms / 1000.0  # 转换为秒
                logger.info(f"从DBC获取消息 {message_name} 的周期: {period}秒")
            else:
                logger.error(f"DBC中未找到消息 {message_name} 的周期，且未提供周期参数")
                return None
        elif period is None:
            logger.error("未指定周期且未加载DBC文件")
            return None
        try:
            # 获取message_id
            if not self.dbc_database:
                logger.error("未加载DBC文件，无法获取message_id")
                return None
            
            message_info = self.dbc_database.get_message_by_name(message_name)
            if not message_info:
                logger.error(f"未找到消息: {message_name}")
                return None
            
            message_id = message_info.frame_id
            
            # 创建任务配置
            task_config = {
                'message_name': message_name,
                'message_id': message_id,  # 存储message_id
                'signal_values': signal_values.copy(),
                'period': period,
                'is_fd': is_fd,
                'rc_byte': rc_byte,
                'rc_start_bit': rc_start_bit,
                'rc_len': rc_len,
                'cs_byte': cs_byte,
                'rolling_count': 0,  # 当前RollingCount值
                'fixed_rc': False,  # 是否固定RollingCount
                'fixed_cs': False,  # 是否固定CheckSum
                'enabled': True     # 任务是否启用
            }
            
            # 启动任务线程
            task_thread = threading.Thread(
                target=self._periodic_task,
                args=(message_id, task_config),
                daemon=True
            )
            
            with self.task_lock:
                self.periodic_tasks[message_id] = {
                    'config': task_config,
                    'thread': task_thread
                }
            
            task_thread.start()
            logger.info(f"添加周期性任务成功，MessageID: 0x{message_id:X}, 消息: {message_name}, 周期: {period}秒")
            return message_id
            
        except Exception as e:
            logger.error(f"添加周期性任务失败: {e}")
            return None
            
    def _periodic_task(self, message_id, task_config):
        """周期性任务线程函数
        
        Args:
            message_id: 消息ID
            task_config: 任务配置
        """
        try:
            with self.task_lock:
                if message_id not in self.periodic_tasks:
                    return
                current_config = self.periodic_tasks[message_id]['config']
                period = current_config['period']
        except:
            logger.error(f"获取任务配置失败，MessageID: 0x{message_id:X}")
            return
            
        # 使用更高精度的时间函数和基于绝对时间的调度方式
        start_time = time.perf_counter()
        iteration_count = 0
        
        # 定义最小睡眠阈值（Windows上time.sleep的精度通常约为15ms）
        MIN_SLEEP_DURATION = 0.001  # 1ms
        
        # 自适应补偿机制参数
        execution_time_history = []  # 存储最近几次的实际执行时间
        MAX_HISTORY_LENGTH = 5  # 历史记录最大长度
        COMPENSATION_FACTOR = 0.3  # 补偿因子，0表示不补偿，1表示完全补偿
        MAX_COMPENSATION = 0.1  # 最大补偿值（避免过度补偿）
        
        while True:
            try:
                with self.task_lock:
                    if message_id not in self.periodic_tasks:
                        break
                    current_config = self.periodic_tasks[message_id]['config']
                    period = current_config['period']
                    
                if not current_config['enabled']:
                    time.sleep(0.1)  # 任务被禁用，短暂休眠后继续检查
                    continue
                
                iteration_count += 1
                
                # 记录任务开始执行的时间
                task_start_time = time.perf_counter()
                
                # 组装报文数据
                if self.dbc_database:
                    try:
                        # 使用DBC文件组装报文
                        arbitration_id = self.dbc_database.get_message_by_name(current_config['message_name']).frame_id
                        data = self.dbc_database.encode_message(current_config['message_name'], current_config['signal_values'])
                        data = list(data)
                        
                        # 应用RollingCount和CheckSum计算（如果配置了相关参数且未固定）
                        if (all(param is not None for param in [current_config['rc_byte'], 
                                                              current_config['rc_start_bit'], 
                                                              current_config['rc_len'], 
                                                              current_config['cs_byte']])):
                            
                            # 调用本地实现的tx_rc_checksum_cal函数
                            data, new_rc = tx_rc_checksum_cal(
                                a_dlc=len(data),
                                data=data,
                                rc_byte=current_config['rc_byte'],
                                rc_start_bit=current_config['rc_start_bit'],
                                rc_len=current_config['rc_len'],
                                cs_byte=current_config['cs_byte'],
                                current_rc=current_config['rolling_count'],
                                rc_right_flag=not current_config['fixed_rc'],
                                cs_right_flag=not current_config['fixed_cs']
                            )
                            
                            # 更新任务配置中的RollingCount值
                            with self.task_lock:
                                self.periodic_tasks[message_id]['config']['rolling_count'] = new_rc
                        
                        # 发送消息
                        success = self.vector.send_message(arbitration_id, data, is_fd=current_config['is_fd'])
                        
                    except Exception as e:
                        logger.error(f"报文组装失败: {e}")
                        success = False
                else:
                    logger.error("未加载DBC文件")
                    success = False
                
                if not success:
                    logger.warning(f"周期性任务 0x{message_id:X} 发送失败")
                
                # 计算任务实际执行时间
                task_end_time = time.perf_counter()
                actual_execution_time = task_end_time - task_start_time
                
                # 更新执行时间历史
                execution_time_history.append(actual_execution_time)
                if len(execution_time_history) > MAX_HISTORY_LENGTH:
                    execution_time_history.pop(0)  # 保持历史记录长度
                
                # 计算下一次发送的绝对时间点
                next_send_time = start_time + (iteration_count + 1) * period
                
                # 计算基本等待时间
                current_time = time.perf_counter()
                base_sleep_duration = next_send_time - current_time
                
                # 计算自适应补偿
                adaptive_compensation = 0.0
                if execution_time_history:
                    # 计算平均执行时间
                    avg_execution_time = sum(execution_time_history) / len(execution_time_history)
                    
                    # 根据平均执行时间与理想执行时间的偏差计算补偿
                    # 这里假设理想执行时间为0，实际执行时间越长，补偿应该越大
                    adaptive_compensation = avg_execution_time * COMPENSATION_FACTOR
                    
                    # 限制补偿值的范围
                    adaptive_compensation = max(0, min(adaptive_compensation, MAX_COMPENSATION))
                
                # 应用补偿后的等待时间
                sleep_duration = base_sleep_duration - adaptive_compensation
                
                # 确保等待时间不为负
                sleep_duration = max(0, sleep_duration)
                
                if sleep_duration > MIN_SLEEP_DURATION:
                    # 如果剩余时间足够，使用time.sleep
                    time.sleep(sleep_duration)
                elif sleep_duration > 0:
                    # 如果剩余时间很小，使用忙等待以获得更高精度
                    while time.perf_counter() < next_send_time:
                        pass
                else:
                    # 如果已经超过了计划时间，记录警告并继续下一个周期
                    logger.warning(f"周期性任务 0x{message_id:X} 执行超时: {abs(sleep_duration):.6f}秒")
                
            except Exception as e:
                logger.error(f"周期性任务 0x{message_id:X} 出错: {e}")
                time.sleep(0.1)  # 出错后短暂休眠，避免无限循环
                
    def update_signal_value(self, message_id, signal_name, value):
        """更新周期性消息的信号值
        
        Args:
            message_id: 消息ID
            signal_name: 信号名称
            value: 新的信号值
            
        Returns:
            bool: 更新成功返回True，失败返回False
        """
        try:
            with self.task_lock:
                if message_id not in self.periodic_tasks:
                    logger.error(f"MessageID 0x{message_id:X} 不存在")
                    return False
                    
                task_config = self.periodic_tasks[message_id]['config']
                
                if signal_name not in task_config['signal_values']:
                    logger.error(f"信号名称 {signal_name} 不存在于MessageID 0x{message_id:X}")
                    return False
                    
                # 更新信号值
                task_config['signal_values'][signal_name] = value
                
                # 记录信号更新结果到文件
                signal_update_log_path = os.path.join(os.path.dirname(__file__), "signal_update_log.txt")
                with open(signal_update_log_path, "a") as log_file:
                    log_file.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] 单个更新: MessageID 0x{message_id:X}, {signal_name} -> {value}\n")
                
                logger.info(f"更新MessageID 0x{message_id:X} 的信号 {signal_name} 为 {value}")
                return True
                
        except Exception as e:
            logger.error(f"更新信号值失败: {e}")
            return False
            
    def update_signal_values(self, message_id, signal_values_dict):
        """批量更新周期性消息的信号值
        
        Args:
            message_id: 消息ID
            signal_values_dict: 信号值字典，key为信号名称，value为新的信号值
            
        Returns:
            bool: 更新成功返回True，失败返回False
        """
        try:
            with self.task_lock:
                if message_id not in self.periodic_tasks:
                    logger.error(f"MessageID 0x{message_id:X} 不存在")
                    return False
                    
                task_config = self.periodic_tasks[message_id]['config']
                
                # 记录实际更新的信号值
                updated_signals = {}
                for signal_name, value in signal_values_dict.items():
                    if signal_name in task_config['signal_values']:
                        task_config['signal_values'][signal_name] = value
                        updated_signals[signal_name] = value
                    else:
                        logger.warning(f"信号名称 {signal_name} 不存在于MessageID 0x{message_id:X}")
                
                # 记录信号更新结果到文件
                if updated_signals:
                    signal_update_log_path = os.path.join(os.path.dirname(__file__), "signal_update_log.txt")
                    with open(signal_update_log_path, "a") as log_file:
                        log_file.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] 批量更新: MessageID 0x{message_id:X}, {updated_signals}\n")
                
                logger.info(f"批量更新MessageID 0x{message_id:X} 的信号值: {signal_values_dict}")
                return True
                
        except Exception as e:
            logger.error(f"批量更新信号值失败: {e}")
            return False
            
    def set_fixed_rolling_count(self, message_id, fixed=True):
        """设置是否固定RollingCount
        
        Args:
            message_id: 消息ID
            fixed: True表示固定，False表示自动更新
            
        Returns:
            bool: 设置成功返回True，失败返回False
        """
        try:
            with self.task_lock:
                if message_id not in self.periodic_tasks:
                    logger.error(f"MessageID 0x{message_id:X} 不存在")
                    return False
                    
                self.periodic_tasks[message_id]['config']['fixed_rc'] = fixed
                logger.info(f"设置MessageID 0x{message_id:X} 的RollingCount {'固定' if fixed else '自动更新'}")
                return True
                
        except Exception as e:
            logger.error(f"设置固定RollingCount失败: {e}")
            return False
            
    def set_fixed_checksum(self, message_id, fixed=True):
        """设置是否固定CheckSum
        
        Args:
            message_id: 消息ID
            fixed: True表示固定，False表示自动计算
            
        Returns:
            bool: 设置成功返回True，失败返回False
        """
        try:
            with self.task_lock:
                if message_id not in self.periodic_tasks:
                    logger.error(f"MessageID 0x{message_id:X} 不存在")
                    return False
                    
                self.periodic_tasks[message_id]['config']['fixed_cs'] = fixed
                logger.info(f"设置MessageID 0x{message_id:X} 的CheckSum {'固定' if fixed else '自动计算'}")
                return True
                
        except Exception as e:
            logger.error(f"设置固定CheckSum失败: {e}")
            return False
            
    def enable_task(self, message_id, enable=True):
        """启用或禁用周期性任务
        
        Args:
            message_id: 消息ID
            enable: True表示启用，False表示禁用
            
        Returns:
            bool: 设置成功返回True，失败返回False
        """
        try:
            with self.task_lock:
                if message_id not in self.periodic_tasks:
                    logger.error(f"MessageID 0x{message_id:X} 不存在")
                    return False
                    
                self.periodic_tasks[message_id]['config']['enabled'] = enable
                logger.info(f"MessageID 0x{message_id:X} {'已启用' if enable else '已禁用'}")
                return True
                
        except Exception as e:
            logger.error(f"启用/禁用任务失败: {e}")
            return False
            
    def remove_task(self, message_id):
        """移除周期性任务
        
        Args:
            message_id: 消息ID
            
        Returns:
            bool: 移除成功返回True，失败返回False
        """
        try:
            with self.task_lock:
                if message_id not in self.periodic_tasks:
                    logger.error(f"MessageID 0x{message_id:X} 不存在")
                    return False
                    
                del self.periodic_tasks[message_id]
            
            logger.info(f"移除周期性任务成功，MessageID: 0x{message_id:X}")
            return True
            
        except Exception as e:
            logger.error(f"移除周期性任务失败: {e}")
            return False
            
    def stop_all_tasks(self):
        """停止所有周期性任务"""
        try:
            with self.task_lock:
                for message_id in list(self.periodic_tasks.keys()):
                    del self.periodic_tasks[message_id]
            
            logger.info("停止所有周期性任务成功")
            return True
            
        except Exception as e:
            logger.error(f"停止所有周期性任务失败: {e}")
            return False
            
    def shutdown(self):
        """关闭消息调度器"""
        self.stop_all_tasks()
        self.vector.shutdown()
        logger.info("消息调度器已关闭")


# 示例用法
if __name__ == "__main__":
    import sys
    import os
    import json
    
    # 添加项目根目录到Python路径
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    sys.path.append(project_root)
    
    # 创建测试结果文件
    result_file_path = os.path.join(os.path.dirname(__file__), "signal_update_result.txt")
    result_file = open(result_file_path, "w")
    
    def log_to_file(message):
        """将日志同时输出到控制台和文件"""
        print(message)
        result_file.write(message + "\n")
        result_file.flush()  # 确保立即写入文件
    
    log_to_file("=" * 60)
    log_to_file("MessageScheduler 完整功能验证")
    log_to_file("=" * 60)
    
    try:
        # 1. 测试构造函数
        log_to_file("\n1. 测试构造函数")
        scheduler = MessageScheduler(channel=0, bitrate=500000)
        log_to_file("   [OK] MessageScheduler实例创建成功")
        
        # 2. 测试连接CAN设备
        log_to_file("\n2. 测试连接CAN设备")
        if scheduler.connect():
            log_to_file("   [OK] CAN设备连接成功")
        else:
            log_to_file("   [WARNING] CAN设备连接失败（可能没有实际硬件）")
            log_to_file("   继续测试其他功能...")
        
        # 3. 测试加载DBC文件
        log_to_file("\n3. 测试加载DBC文件")
        dbc_path = r"E:\workspace\01_ABS\03_N001\Files\SGMW_N001_ABS_20250919_V1.0.dbc"
        if os.path.exists(dbc_path):
            if scheduler.load_dbc(dbc_path):
                log_to_file("   [OK] DBC文件加载成功")
            else:
                log_to_file("   [ERROR] DBC文件加载失败")
        else:
            log_to_file("   [WARNING] DBC文件不存在，跳过DBC相关测试")
        
        # 4. 测试加载配置文件
        log_to_file("\n4. 测试加载配置文件")
        config_path = os.path.join(os.path.dirname(__file__), r"./messages_info.json")
        if os.path.exists(config_path):
            if scheduler.load_config(config_path):
                log_to_file("   [OK] 配置文件加载成功")
            else:
                log_to_file("   [ERROR] 配置文件加载失败")
        else:
            log_to_file("   [WARNING] 配置文件不存在，跳过配置相关测试")
        
        # 5. 测试发送初始消息
        log_to_file("\n5. 测试发送初始消息")
        try:
            scheduler.start_initial_messages()
            log_to_file("   [OK] 初始消息发送完成")
        except Exception as e:
            log_to_file(f"   [WARNING] 发送初始消息时出错: {e}")
        
        # 6. 测试启动周期性消息
        log_to_file("\n6. 测试启动周期性消息")
        message_ids = scheduler.start_periodic_messages()
        log_to_file(f"   [OK] 启动了 {len(message_ids)} 个周期性任务")

        
        if message_ids:
            # 7. 测试批量更新信号值
            log_to_file("\n7. 测试批量更新信号值")
            first_message_id = message_ids[0]
            log_to_file(f"   等待2秒后更新MessageID 0x{first_message_id:X}的信号值...")
            time.sleep(2)
            
            # 根据messages_info.json，使用实际存在的信号名称
            signal_values = {}
            if first_message_id == 0x341:  # HEV_General_Status_1
                signal_values["HandBrkSts"] = 1
            elif first_message_id == 0x1B9:  # HCU_General_Status_2
                signal_values["AccActPosV"] = 50
                signal_values["VrtlAccPstnV"] = 30
            
            log_to_file(f"   尝试更新的信号值: {signal_values}")
            if signal_values:
                if scheduler.update_signal_values(first_message_id, signal_values):
                    log_to_file("   [OK] 批量更新信号值成功")
                else:
                    log_to_file("   [WARNING] 批量更新信号值失败")
            else:
                log_to_file(f"   [WARNING] 没有为MessageID 0x{first_message_id:X}配置测试信号")
            
            # 8. 测试单个更新信号值
            log_to_file("\n8. 测试单个更新信号值")
            test_success = False
            if first_message_id == 0x341:
                if scheduler.update_signal_value(first_message_id, "HandBrkSts", 0):
                    log_to_file("   [OK] 单个更新信号值成功 (HandBrkSts -> 0)")
                    test_success = True
                else:
                    log_to_file("   [WARNING] 单个更新信号值失败 (HandBrkSts -> 0)")
            elif first_message_id == 0x1B9:
                if scheduler.update_signal_value(first_message_id, "AccActPosV", 20):
                    log_to_file("   [OK] 单个更新信号值成功 (AccActPosV -> 20)")
                    test_success = True
                else:
                    log_to_file("   [WARNING] 单个更新信号值失败 (AccActPosV -> 20)")
            else:
                log_to_file(f"   [WARNING] 没有为MessageID 0x{first_message_id:X}配置测试信号")
            
            # 写入信号更新结果到文件
            if test_success:
                log_to_file("\n[总结] 信号更新功能测试通过！")
            else:
                log_to_file("\n[总结] 信号更新功能测试失败！")
            
            # 9. 测试固定RollingCount
            log_to_file("\n9. 测试固定RollingCount")
            if scheduler.set_fixed_rolling_count(first_message_id, True):
                log_to_file("   [OK] 设置固定RollingCount成功")
            else:
                log_to_file("   [WARNING] 设置固定RollingCount失败")
            time.sleep(10)
            
            # 10. 测试固定CheckSum
            log_to_file("\n10. 测试固定CheckSum")
            if scheduler.set_fixed_checksum(first_message_id, True):
                log_to_file("   [OK] 设置固定CheckSum成功")
            else:
                log_to_file("   [WARNING] 设置固定CheckSum失败")
            time.sleep(10)
            # 11. 测试启用/禁用任务
            log_to_file("\n11. 测试禁用任务")
            if scheduler.enable_task(first_message_id, False):
                log_to_file("   [OK] 禁用任务成功")
                
                log_to_file("\n11.1 测试启用任务")
                if scheduler.enable_task(first_message_id, True):
                    log_to_file("   [OK] 启用任务成功")
                else:
                    log_to_file("   [WARNING] 启用任务失败")
            else:
                log_to_file("   [WARNING] 禁用任务失败")
            
            # 12. 测试停止所有任务
            log_to_file("\n12. 测试停止所有任务")
            log_to_file("   等待2秒后停止所有任务...")
            time.sleep(2)
            scheduler.stop_all_tasks()
            log_to_file("   [OK] 停止所有任务成功")
            
            # 13. 测试添加周期性消息
            log_to_file("\n13. 测试添加周期性消息")
            if hasattr(scheduler, 'dbc_database') and scheduler.dbc_database:
                # 只有加载了DBC文件才能测试添加周期性消息
                try:
                    # 假设DBC中有HEV_General_Status_1消息
                    new_message_id = scheduler.add_periodic_message(
                        message_name="HEV_General_Status_1",
                        signal_values={"HandBrkSts": 0},
                        period=0.5,  # 500ms
                        is_fd=False
                    )
                    
                    if new_message_id:
                        log_to_file(f"   [OK] 添加周期性消息成功，MessageID: 0x{new_message_id:X}")
                        
                        # 14. 测试移除任务
                        log_to_file("\n14. 测试移除任务")
                        time.sleep(1)
                        if scheduler.remove_task(new_message_id):
                            log_to_file("   [OK] 移除任务成功")
                        else:
                            log_to_file("   [WARNING] 移除任务失败")
                    else:
                        log_to_file("   [WARNING] 添加周期性消息失败")
                except Exception as e:
                    log_to_file(f"   [WARNING] 添加周期性消息时出错: {e}")
            else:
                log_to_file("   [WARNING] 未加载DBC文件，跳过添加周期性消息测试")
        
        # 15. 测试重新启动周期性消息
        log_to_file("\n15. 测试重新启动周期性消息")
        message_ids = scheduler.start_periodic_messages()
        log_to_file(f"   [OK] 重新启动了 {len(message_ids)} 个周期性任务")
        
        # 等待1秒，让周期性消息发送几次
        time.sleep(1)
        
        # 停止所有任务
        scheduler.stop_all_tasks()
        
        log_to_file("\n" + "=" * 60)
        log_to_file("所有功能验证完成！")
        log_to_file("\n注意：")
        log_to_file("- 如果看到'[WARNING]'标记，表示该功能可能需要实际硬件支持")
        log_to_file("- 如果看到'[ERROR]'标记，表示该功能出现错误")
        log_to_file("- 如果看到'[OK]'标记，表示该功能测试通过")
        log_to_file("=" * 60)
        
        # 关闭结果文件
        result_file.close()
        log_to_file(f"\n测试结果已写入 {result_file_path} 文件")
        
        print("\n程序将自动退出...")
            
    except KeyboardInterrupt:
        print("\n\n用户中断程序")
    except Exception as e:
        print(f"\n\n程序异常: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if 'scheduler' in locals():
            print("\n清理资源...")
            if hasattr(scheduler, 'stop_all_tasks'):
                scheduler.stop_all_tasks()
            if hasattr(scheduler, 'shutdown'):
                scheduler.shutdown()
        print("程序退出")
