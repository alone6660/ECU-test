# -*- coding: utf-8 -*-

import time
import logging
import sys
import os
from typing import Any, Optional, Tuple, Dict, Union
from py_canoe import CANoe

# 添加项目根目录到Python路径
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(project_root)

# 导入logger模块
from logger.logger import setup_logging



# 导入密钥生成模块
from security.seedkey import generate_key_from_seed

# 诊断服务常量
DIAG_SERVICE_READ_DATA_BY_IDENTIFIER = '22'
DIAG_SERVICE_SECURITY_ACCESS = '27'
DIAG_SERVICE_SECURITY_ACCESS_REQUEST_SEED = '27 01'
DIAG_SERVICE_SECURITY_ACCESS_SEND_KEY = '27 02'
# 高级解锁级别服务
DIAG_SERVICE_SECURITY_ACCESS_REQUEST_SEED_LEVEL5 = '27 05'
DIAG_SERVICE_SECURITY_ACCESS_SEND_KEY_LEVEL5 = '27 06'
DIAG_SERVICE_START_DIAG_SESSION = '10'

# 解锁级别常量
UNLOCK_LEVEL_1 = 1
UNLOCK_LEVEL_5 = 5

class CANoeSingleton:
    """
    CANoe 单例类，确保全局只有一个 CANoe 实例
    """
    _instance: Optional['CANoeSingleton'] = None
    _initialized: bool = False

    def __new__(cls, *args: Any, **kwargs: Any) -> 'CANoeSingleton':
        if not cls._instance:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(
        self,
        user_capl_functions: Tuple[str, ...] = ('K15_ON', 'K15_OFF', 'rc_stop', 'cs_stop', 'rc_start', 'cs_start', 'sendmessage'),
        canoe_cfg: str = r'E:\workspace\Autotest\Canoe\00_Project\E112C_ABS30_12.cfg',
        logger: Optional[logging.Logger] = None
    ) -> None:
        if not self._initialized:
            # 初始化日志
            self.logger = setup_logging()
            
            # 初始化CANoe实例
            try:
                self._canoe_inst = CANoe(user_capl_functions=user_capl_functions)
                self._canoe_inst.open(canoe_cfg=canoe_cfg)
                self.__class__._initialized = True
                self.logger.info(f"CANoe实例已成功初始化，配置文件: {canoe_cfg}")
            except Exception as e:
                self.logger.error(f"CANoe实例初始化失败: {str(e)}")
                raise

    def __enter__(self) -> 'CANoeSingleton':
        """支持上下文管理器"""
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """上下文退出时关闭CANoe实例"""
        self.close()

    def start_measurement(self, delay: int = 2) -> bool:
        """
        开始测量并编译所有 CAPL 节点
        
        参数:
            delay: 开始测量后的延迟时间（秒）
            
        返回:
            bool: 操作是否成功
        """
        try:
            self._canoe_inst.start_measurement()
            time.sleep(delay)
            self._canoe_inst.compile_all_capl_nodes()
            self.logger.info(f"测量已开始，延迟时间: {delay}秒")
            return True
        except Exception as e:
            self.logger.error(f"开始测量失败: {str(e)}")
            return False

    def send_diagnostic_request(self, request: str, ecu_name: str = 'DIAG_PHY') -> Optional[Any]:
        """
        发送诊断请求
        
        参数:
            request: 诊断请求字符串
            ecu_name: ECU名称
            
        返回:
            诊断响应，如果失败则返回None
        """
        try:
            response = self._canoe_inst.send_diag_request(ecu_name, request, return_sender_name=False)
            self.logger.debug(f"向ECU {ecu_name}发送诊断请求: {request}，响应: {response}")
            return response
        except Exception as e:
            self.logger.error(f"发送诊断请求失败 ({ecu_name}): {request}, 错误: {str(e)}")
            return None

    def unlock_ecu(self, unlock_level: int = UNLOCK_LEVEL_1, ecu_name: str = 'DIAG_PHY') -> Optional[Any]:
        """
        执行27服务解锁
        
        参数:
            unlock_level: 解锁级别 (1或5)
            ecu_name: ECU名称
            
        返回:
            解锁响应，如果失败则返回None
        """
        try:
            # 根据解锁级别选择不同的诊断服务
            if unlock_level == UNLOCK_LEVEL_1:
                request_seed_service = DIAG_SERVICE_SECURITY_ACCESS_REQUEST_SEED
                send_key_service = DIAG_SERVICE_SECURITY_ACCESS_SEND_KEY
            elif unlock_level == UNLOCK_LEVEL_5:
                request_seed_service = DIAG_SERVICE_SECURITY_ACCESS_REQUEST_SEED_LEVEL5
                send_key_service = DIAG_SERVICE_SECURITY_ACCESS_SEND_KEY_LEVEL5
            else:
                self.logger.error(f"不支持的解锁级别: {unlock_level}")
                return None
            
            # 发送请求种子命令
            seed_response = self.send_diagnostic_request(request_seed_service, ecu_name)
            if seed_response is None:
                self.logger.error(f"获取ECU {ecu_name}种子失败")
                return None
                
            # 提取种子数据
            if isinstance(seed_response, str):
                # 跳过前5个字符，提取实际种子数据
                seed_str = seed_response[5:]
                # 将种子字符串转换为整数列表（去除空格并转换为十六进制整数）
                seed_data = [int(byte, 16) for byte in seed_str.split()]
            elif isinstance(seed_response, list):
                seed_data = seed_response[5:]  # 假设是列表格式
            else:
                self.logger.error(f"种子响应格式不支持: {type(seed_response)}")
                return None
                
            # 生成密钥
            key = generate_key_from_seed(seed_data, unlock_level)
            if key is None:
                self.logger.error(f"生成密钥失败，种子: {seed_data}, 解锁级别: {unlock_level}")
                return None
                
            # 转换密钥格式：将十六进制列表转换为诊断请求格式（例如：['0x53', '0x88'] -> '53 88'）
            key_hex_str = ' '.join([hex_val[2:] for hex_val in key])
            
            # 发送密钥
            key_request = f"{send_key_service} {key_hex_str}"
            unlock_response = self.send_diagnostic_request(key_request, ecu_name)
            
            if unlock_response:
                self.logger.info(f"ECU {ecu_name}解锁成功，级别: {unlock_level}")
            else:
                self.logger.error(f"ECU {ecu_name}解锁失败，级别: {unlock_level}")
                
            return unlock_response
            
        except Exception as e:
            self.logger.error(f"ECU {ecu_name}解锁失败，级别: {unlock_level}, 错误: {str(e)}")
            return None

    def get_can_bus_statistics(self, channel: int = 1) -> Optional[Dict[str, Any]]:
        """
        获取指定 CAN 通道的统计信息
        
        参数:
            channel: CAN通道号
            
        返回:
            CAN总线统计信息字典，如果失败则返回None
        """
        try:
            statistics = self._canoe_inst.get_can_bus_statistics(channel=channel)
            self.logger.debug(f"获取CAN通道 {channel} 的统计信息: {statistics}")
            return statistics
        except Exception as e:
            self.logger.error(f"获取CAN通道 {channel} 的统计信息失败: {str(e)}")
            return None

    def start_diagnostic_session(self, session_type: str = '02', ecu_name: str = 'DIAG_PHY') -> Optional[Any]:
        """
        启动诊断会话
        
        参数:
            session_type: 会话类型
            ecu_name: ECU名称
            
        返回:
            会话响应，如果失败则返回None
        """
        request = f"{DIAG_SERVICE_START_DIAG_SESSION} {session_type}"
        return self.send_diagnostic_request(request, ecu_name)

    def read_data_by_identifier(self, did: str, ecu_name: str = 'DIAG_PHY') -> Optional[Any]:
        """
        读取数据标识符
        
        参数:
            did: 数据标识符
            ecu_name: ECU名称
            
        返回:
            数据响应，如果失败则返回None
        """
        request = f"{DIAG_SERVICE_READ_DATA_BY_IDENTIFIER} {did}"
        return self.send_diagnostic_request(request, ecu_name)

    def set_signal_value(self, bus: str, channel: int, message: str, signal: str, value: Any, raw_value: bool = False) -> bool:
        """
        设置信号值
        
        参数:
            bus: 总线类型（如'CAN'）
            channel: 通道号
            message: 消息名称
            signal: 信号名称
            value: 要设置的值
            raw_value: 是否使用原始值
            
        返回:
            bool: 操作是否成功
        """
        try:
            self._canoe_inst.set_signal_value(bus=bus, channel=channel, message=message, signal=signal, value=value, raw_value=raw_value)
            self.logger.debug(f"设置信号值成功: {bus}/{channel}/{message}/{signal} = {value} (raw_value={raw_value})")
            return True
        except Exception as e:
            self.logger.error(f"设置信号值失败: {bus}/{channel}/{message}/{signal}, 错误: {str(e)}")
            return False

    def get_signal_value(self, bus: str, channel: int, message: str, signal: str, raw_value: bool = False) -> Optional[Any]:
        """
        获取信号值
        
        参数:
            bus: 总线类型（如'CAN'）
            channel: 通道号
            message: 消息名称
            signal: 信号名称
            raw_value: 是否使用原始值
            
        返回:
            信号值，如果失败则返回None
        """
        try:
            value = self._canoe_inst.get_signal_value(bus=bus, channel=channel, message=message, signal=signal, raw_value=raw_value)
            self.logger.debug(f"获取信号值成功: {bus}/{channel}/{message}/{signal} = {value} (raw_value={raw_value})")
            return value
        except Exception as e:
            self.logger.error(f"获取信号值失败: {bus}/{channel}/{message}/{signal}, 错误: {str(e)}")
            return None

    def call_capl_function(self, function_name: str, *args: Any) -> Optional[Any]:
        """
        调用CAPL函数
        
        参数:
            function_name: CAPL函数名称
            *args: 函数参数
            
        返回:
            CAPL函数返回值，如果失败则返回None
        """
        try:
            result = self._canoe_inst.call_capl_function(function_name, *args)
            self.logger.debug(f"调用CAPL函数成功: {function_name}{args}, 返回值: {result}")
            return result
        except Exception as e:
            self.logger.error(f"调用CAPL函数失败: {function_name}{args}, 错误: {str(e)}")
            return None

    # 测量控制方法
    def stop_measurement(self) -> bool:
        """
        停止测量
        
        返回:
            bool: 操作是否成功
        """
        try:
            self._canoe_inst.stop_measurement()
            self.logger.info("测量已停止")
            return True
        except Exception as e:
            self.logger.error(f"停止测量失败: {str(e)}")
            return False

    def close(self) -> None:
        """关闭 CANoe 实例"""
        if hasattr(self, '_canoe_inst') and self.__class__._initialized:
            try:
                self._canoe_inst.quit()
                self.logger.info("CANoe实例已关闭")
            except Exception as e:
                self.logger.error(f"关闭CANoe实例失败: {str(e)}")
            finally:
                self.__class__._initialized = False
                self.__class__._instance = None


if __name__ == '__main__':
    print("=== 开始测试CANoe_Software中的所有方法 ===")
    
    try:
        # 创建CANoe实例
        print("1. 创建CANoe实例...")
        canoe = CANoeSingleton(canoe_cfg=r"E:\workspace\Autotest\Canoe\00_Project\F520M_ESC20\F520M_ESC20_12.cfg")
        print("✓ CANoe实例创建成功")
        
        # 开始测量
        print("\n3. 测试start_measurement()方法...")
        if canoe.start_measurement():
            print("✓ 测量已成功开始")
        else:
            print("✗ 测量开始失败")
        
        # 获取CAN总线统计信息
        print("\n4. 测试get_can_bus_statistics()方法...")
        stats = canoe.get_can_bus_statistics(channel=1)
        if stats:
            print(f"✓ CAN总线统计信息获取成功: {stats}")
        else:
            print("✗ CAN总线统计信息获取失败")
        
        # 测试set_signal_value方法
        print("\n5. 测试set_signal_value()方法...")
        success = canoe.set_signal_value(bus='CAN', channel=1, message='HCU_General_Status_2', signal='HCUGnrlSts2RollCnt', value=2, raw_value=False)
        if success:
            print("✓ 设置信号值成功")
        else:
            print("✗ 设置信号值失败")
        
        # 测试get_signal_value方法
        print("\n6. 测试get_signal_value()方法...")
        value = canoe.get_signal_value(bus='CAN', channel=1, message='HCU_General_Status_2', signal='HCUGnrlSts2RollCnt', raw_value=False)
        if value is not None:
            print(f"✓ 获取信号值成功: {value}")
        else:
            print("✗ 获取信号值失败")
        
        # 测试call_capl_function方法
        print("\n7. 测试call_capl_function()方法...")
        try:
            result = canoe.call_capl_function("K15_OFF")
            print(f"✓ 调用CAPL函数成功: {result}")
            time.sleep(10)
            result = canoe.call_capl_function("K15_ON")
            print(f"✓ 调用CAPL函数成功: {result}")
        except Exception as e:
            print(f"✗ 调用CAPL函数失败: {e}")
        
        # 测试start_diagnostic_session方法
        print("\n8. 测试start_diagnostic_session()方法...")
        time.sleep(1)
        session_response = canoe.start_diagnostic_session(session_type='03')
        if session_response is not None:
            print(f"✓ 启动诊断会话成功: {session_response}")
        else:
            print("✗ 启动诊断会话失败")
        
        # 测试read_data_by_identifier方法
        print("\n9. 测试read_data_by_identifier()方法...")
        did_response = canoe.read_data_by_identifier("202B")
        if did_response is not None:
            print(f"✓ 读取DID成功: {did_response}")
        else:
            print("✗ 读取DID失败")

        # 测试send_diagnostic_request方法
        print("\n10. 测试send_diagnostic_request()方法...")
        diag_response = canoe.send_diagnostic_request("10 03")
        if diag_response is not None:
            print(f"✓ 发送诊断请求成功: {diag_response}")
        else:
            print("✗ 发送诊断请求失败")
        
        # 测试unlock_ecu方法
        print("\n11. 测试unlock_ecu()方法...")
        unlock_response = canoe.unlock_ecu(unlock_level=1)
        if unlock_response is not None:
            print(f"✓ ECU解锁成功: {unlock_response}")
        else:
            print("✗ ECU解锁失败")
        
        # 停止测量
        print("\n12. 测试stop_measurement()方法...")
        if canoe.stop_measurement():
            print("✓ 测量已成功停止")
        else:
            print("✗ 测量停止失败")
        
    except Exception as e:
        print(f"\n✗ 测试过程中发生错误: {e}")
    finally:
        # 手动关闭CANoe实例
        print("\n关闭CANoe实例...")

        print("✓ CANoe实例已关闭")
    
    print("\n=== 所有方法测试完成 ===")

    
