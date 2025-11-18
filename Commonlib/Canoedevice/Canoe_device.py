import time
from py_canoe import CANoe
from typing import Any, Optional, Tuple

from Commonlib.script.seedkey import seed_to_key_sgmw_str


class CANoeSingleton:
    """
    CANoe 单例类，确保整个应用中只有一个 CANoe 实例。
    """
    _instance: Optional['CANoeSingleton'] = None
    _initialized: bool = False

    def __new__(cls, *args: Any, **kwargs: Any) -> 'CANoeSingleton':
        if not cls._instance:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(
        self,
        user_capl_functions: Tuple[str, ...] = ('K15_ON', 'K15_OFF', 'rc_stop', 'cs_stop', 'rc_start', 'cs_start','sendmessage'),
        canoe_cfg: str = r'E:\workspace\Autotest\Canoe\00_Project\E112C_ABS30_12.cfg'
    ) -> None:
        if not self._initialized:
            self._canoe_inst = CANoe(user_capl_functions=user_capl_functions)
            self._canoe_inst.open(canoe_cfg=canoe_cfg)
            self.__class__._initialized = True

    def start_measurement(self, delay: int = 2) -> None:
        """启动测量并编译所有 CAPL 节点。"""
        self._canoe_inst.start_measurement()
        time.sleep(delay)
        self._canoe_inst.compile_all_capl_nodes()

    def diag_PHY(self, diag_request: str,diag_ecu_name: str = 'DIAG_PHY') -> Any:
        """发送诊断请求。"""
        return self._canoe_inst.send_diag_request(diag_ecu_name, diag_request)

    def diag_lock27(self,diag_ecu_name: str = 'DIAG_PHY') -> Any:
        """27lock。"""
        seed = self._canoe_inst.send_diag_request(diag_ecu_name, '27 01', return_sender_name=False)
        key = seed_to_key_sgmw_str(seed[5:])
        resp = self._canoe_inst.send_diag_request(diag_ecu_name, '27 02 '+key, return_sender_name=False)
    def get_can_bus_statistics(self, channel: int = 1) -> Any:
        """获取指定通道的 CAN 总线统计信息。"""
        return self._canoe_inst.get_can_bus_statistics(channel=channel)

    # 显式定义其他可能需要的方法
    def stop_measurement(self) -> None:
        """停止测量。"""
        self._canoe_inst.stop_measurement()

    def close(self) -> None:
        """关闭 CANoe 实例。"""
        if hasattr(self, '_canoe_inst'):
            self._canoe_inst.close()
            self.__class__._initialized = False
            self.__class__._instance = None


if __name__ == '__main__':
    # 使用单例类
    canoe = CANoeSingleton(canoe_cfg=r"E:\workspace\Autotest\Canoe\00_Project\F520M_ESC20\F520M_ESC20_12.cfg")

    # 启动测量并编译所有节点
    canoe.start_measurement()

    # 获取CAN总线统计信息
    canoe.get_can_bus_statistics(channel=1)
    for i in  range(1000):
        time.sleep(0.1)
        canoe._canoe_inst.set_signal_value(bus='CAN', channel=1, message='HCU_General_Status_2', signal='HCUGnrlSts2RollCnt', value=2, raw_value=False)
    # for i in  range(1000):
    #     a=canoe._canoe_inst.get_signal_value(bus='CAN', channel=1, message='PPEI_Chassis_General_Status_1', signal='PPEI_Chas_Gen_Sta_1RC', raw_value=False)
    #     print(a)
    # 执行诊断循环
    # canoe.diag_PHY('1002')
    # F18A = canoe.diag_PHY('22' + "F18A")
    # F188 = canoe.diag_PHY('22' + "F188")
    # F191 = canoe.diag_PHY('22' + "F191")
    # F1CB = canoe.diag_PHY('22' + "F1CB")
    # F192 = canoe.diag_PHY('22' + "F192")
    # F193 = canoe.diag_PHY('22' + "F193")
    # F194 = canoe.diag_PHY('22' + "F194")
    # F195 = canoe.diag_PHY('22' + "F195")
    # DID202C = canoe.diag_PHY('22' + "202C")
    # F1C1 = canoe.diag_PHY('22' + "F1C1")
    # DID202B = canoe.diag_PHY('22' + "202B")
    # F180 = canoe.diag_PHY('22' + "F180")
    # full_data = [0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08]
    # for i in range(10000):
    #     canoe._canoe_inst.call_capl_function("sendmessage",1,0x123,8)
    #     time.sleep(0.200)

    
