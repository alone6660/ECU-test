# -*- coding: utf-8 -*-
import serial
import time
import struct


class HSPY3603PowerController:
    def __init__(self, port='COM6', baudrate=9600, timeout=3):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.ser = None
        self.address = 0x00

    def connect(self):
        """连接电源设备"""
        try:
            # 避免重复打开已关闭的连接
            if self.ser is not None and not self.ser.is_open:
                self.ser = None
            self.ser = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_TWO,
                timeout=self.timeout
            )

            print("设备连接成功")
            return True
        except Exception as e:
            print(f"连接失败: {e}")
            self.ser = None  # 连接失败时确保为None
            return False

    def disconnect(self):
        """关闭电源连接 - 修改版本"""
        if self.ser is not None:
            if self.ser.is_open:
                self.ser.close()
            self.ser = None  # 强制设为None以释放资源
        print("连接已关闭")

    def crc16(self, data_bytes):
        """CRC16校验计算"""
        crc = 0xFFFF
        for byte in data_bytes:
            crc ^= byte
            for _ in range(8):
                if crc & 0x0001:
                    crc = crc >> 1
                    crc ^= 0xA001
                else:
                    crc = crc >> 1
        return crc

    def calculate_crc(self, data):
        """计算CRC校验值"""
        crc_value = self.crc16(data)
        return struct.pack('<H', crc_value)

    def send_command(self, command):
        """发送命令并获取响应"""
        if not self.ser or not self.ser.is_open:
            if not self.connect():
                return None

        # 确保通信间隔时间 > 5ms
        time.sleep(0.006)

        # 清空缓冲区
        self.ser.reset_input_buffer()
        self.ser.reset_output_buffer()

        # 发送命令
        self.ser.write(command)
        time.sleep(0.01)

        # 读取响应
        response = self.ser.read(100)
        return response

    def power_on(self):
        """开启电源输出"""
        command = bytearray([self.address, 0x10, 0x00, 0x04, 0x00, 0x01, 0x02, 0x00, 0x01])
        command.extend(self.calculate_crc(command))
        response = self.send_command(command)
        if response and len(response) >= 8:
            return True
        return False

    def power_off(self):
        """停止电源输出"""
        command = bytearray([self.address, 0x10, 0x00, 0x04, 0x00, 0x01, 0x02, 0x00, 0x00])
        command.extend(self.calculate_crc(command))
        response = self.send_command(command)
        if response and len(response) >= 8:
            return True
        return False

    def set_voltage(self, voltage):
        """设置输出电压"""
        voltage_int = int(voltage * 100)  # 转换为整数倍的2位小数
        command = bytearray([self.address, 0x10, 0x00, 0x00, 0x00, 0x01, 0x02])
        command.extend(struct.pack('>H', voltage_int))  # 高位在前
        command.extend(self.calculate_crc(command))
        response = self.send_command(command)
        if response and len(response) >= 8:
            return True
        return False

    def set_current(self, current):
        """设置输出电流"""
        current_int = int(current * 1000)  # 转换为整数倍的3位小数
        command = bytearray([self.address, 0x10, 0x00, 0x01, 0x00, 0x01, 0x02])
        command.extend(struct.pack('>H', current_int))  # 高位在前
        command.extend(self.calculate_crc(command))
        response = self.send_command(command)
        if response and len(response) >= 8:
            return True
        return False

    def get_voltage_display(self):
        """获取电压显示值 """
        command = bytearray([self.address, 0x03, 0x00, 0x02, 0x00, 0x01])
        command.extend(self.calculate_crc(command))
        response = self.send_command(command)
        if response and len(response) >= 7:
            # 修正处理bytes类型的响应数据
            # 响应格式为地址(1) + 功能码(1) + 字节数(1) + 数据(2) + CRC(2)
            voltage_raw = (response[3] << 8) | response[4]
            return voltage_raw * 0.01  # 转换为实际的电压值
        return None

    def get_current_display(self):
        """获取电流显示值"""
        command = bytearray([self.address, 0x03, 0x00, 0x03, 0x00, 0x01])
        command.extend(self.calculate_crc(command))
        response = self.send_command(command)
        if response and len(response) >= 7:
            current_raw = (response[3] << 8) | response[4]
            return current_raw * 0.001  # 转换为实际的电流值
        return None

    def get_current_setting(self):
        """获取电流设置值"""
        command = bytearray([self.address, 0x03, 0x00, 0x01, 0x00, 0x01])
        command.extend(self.calculate_crc(command))
        response = self.send_command(command)
        if response and len(response) >= 7:
            current_raw = (response[3] << 8) | response[4]
            return current_raw * 0.001  # 转换为实际的电流值
        return None

    def get_power_status(self):
        """获取电源输出状态"""
        command = bytearray([self.address, 0x03, 0x00, 0x04, 0x00, 0x01])
        command.extend(self.calculate_crc(command))
        response = self.send_command(command)
        if response and len(response) >= 7:
            status = response[4]  # 状态信息在第5个字节
            return "开启" if status == 1 else "停止"
        return "未知"

    def get_power_info(self):
        """获取完整的电源信息"""
        info = {}
        info['voltage_display'] = self.get_voltage_display()
        info['current_display'] = self.get_current_display()
        info['current_setting'] = self.get_current_setting()
        info['power_status'] = self.get_power_status()
        return info




if __name__ == "__main__":
    controller = HSPY3603PowerController(port='COM5')
    controller.connect()
    time.sleep(1)
    print(controller.get_current_display())
    time.sleep(1)

    controller.power_on()
    time.sleep(2)

    time.sleep(1)
    controller.disconnect()


    # try:
    #     if controller.connect():
    #         print("设备连接成功")
    #
    #         # 设置电压为12.5V
    #         if controller.set_voltage(12.5):
    #             print("电压设置成功")
    #
    #         # 设置电流为1.5A
    #         if controller.set_current(1.5):
    #             print("电流设置成功")
    #
    #         # 开启电源输出
    #         if controller.power_on():
    #             print("电源开启成功")
    #
    #         # 获取完整的电源信息
    #         power_info = controller.get_power_info()
    #         print("\n=== 电源状态信息 ===")
    #         if power_info['voltage_display'] is not None:
    #             print(f"当前电压: {power_info['voltage_display']:.2f}V")
    #         else:
    #             print("当前电压: 获取失败")
    #
    #         if power_info['current_display'] is not None:
    #             print(f"当前电流: {power_info['current_display']:.3f}A")
    #         else:
    #             print("当前电流: 获取失败")
    #
    #         if power_info['current_setting'] is not None:
    #             print(f"电流设置: {power_info['current_setting']:.3f}A")
    #         else:
    #             print("电流设置: 获取失败")
    #
    #         print(f"电源状态: {power_info['power_status']}")
    #
    # except Exception as e:
    #     print(f"操作出错: {e}")
    #
    # finally:
    #     controller.disconnect()
    #     print("设备已断开连接")