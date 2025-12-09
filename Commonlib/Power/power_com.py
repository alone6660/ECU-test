# -*- coding: utf-8 -*-
import serial.tools.list_ports

from Commonlib.Power.hspy_30_05 import HSPY3603PowerController


def find_power_com_port():
    """自动查找可用的电源设备COM端口"""
    ports = serial.tools.list_ports.comports()
    candidate_ports = []

    for port in ports:
        # 常见的USB转串口设备描述关键词
        common_descriptions = ['USB Serial Port', 'CP210', 'FT232', 'CH340']

        for desc in common_descriptions:
            if desc in port.description:
                candidate_ports.append(port)
                break

    return candidate_ports


def get_available_com_ports():
    """获取所有可用的COM端口"""
    ports = serial.tools.list_ports.comports()
    com_list = []

    for port in ports:
        com_list.append({
            'name': port.name,
            'description': port.description,
            'hardware_id': port.hwid
        })

    return com_list

# 主程序示例使用
if __name__ == "__main__":
    # 获取所有端口
    all_ports = get_available_com_ports()
    print("所有可用的COM端口:")
    for port in all_ports:
        print(f"  {port['name']} - {port['description']}")

    # 尝试连接找到的端口
    for port_info in all_ports:
        try:
            controller = HSPY3603PowerController(port=port_info['name'])
            if controller.connect():
                print(f"成功连接到: {port_info['name']}")
                # 尝试获取电流
                current = controller.get_current_display()
                if current is not None:
                    print(f"  当前电流: {current}A")
                    controller.disconnect()
                    break
        except Exception as e:
            print(f"连接 {port_info['name']} 失败: {e}")