# 32位Python代理脚本 - 用于调用32位DLL
import ctypes
from ctypes import *
import os
import sys
import json
import struct


def get_dll_bitness(dll_path):
    """
    判断DLL文件是32位还是64位
    
    参数:
        dll_path: DLL文件路径
    
    返回:
        int: 32表示32位DLL，64表示64位DLL，None表示无法判断
    """
    try:
        with open(dll_path, 'rb') as f:
            # DOS头（64字节）
            dos_header = f.read(64)
            if len(dos_header) < 64:
                return None
            
            # 检查DOS签名
            if dos_header[:2] != b'MZ':
                return None
            
            # 获取PE头偏移量
            pe_offset = struct.unpack('<L', dos_header[60:64])[0]
            
            # 移动到PE头位置
            f.seek(pe_offset)
            
            # 读取PE签名
            pe_signature = f.read(4)
            if pe_signature != b'PE\x00\x00':
                return None
            
            # 读取机器类型（2字节）
            machine_type = struct.unpack('<H', f.read(2))[0]
            
            # 判断机器类型
            if machine_type == 0x014c:  # IMAGE_FILE_MACHINE_I386
                return 32
            elif machine_type == 0x8664:  # IMAGE_FILE_MACHINE_AMD64
                return 64
            else:
                return None
    
    except Exception:
        return None


def generate_key_from_seed(seed_response, unlock_level=1, dll_path=r'E:\workspace\01_ABS\03_N001\00-canoe\12-CDDDLL\Key_EQ100.dll'):
    """
    使用DLL文件从种子数据生成安全访问密钥
    
    参数:
        seed_response: 种子响应数据列表 (例如: [0x67, 0x01, 0x10, 0x20, 0x30, 0x40])
        unlock_level: 解锁级别，默认值为 1
        dll_path: DLL文件路径，默认值为 'E:\workspace\01_ABS\03_N001\00-canoe\12-CDDDLL\Key_EQ100.dll'
    
    返回:
        dict: 包含调用结果和密钥的字典
    """
    try:
        # 检查DLL文件是否存在
        if not os.path.exists(dll_path):
            return {
                "success": False,
                "error": f"DLL文件不存在: {dll_path}"
            }
        
        # 检测DLL位数
        dll_bits = get_dll_bitness(dll_path)
        if dll_bits == 64:
            return {
                "success": False,
                "error": "代理脚本运行在32位Python环境中，但DLL是64位，无法直接调用"
            }
        
        # 加载DLL文件
        dll = ctypes.WinDLL(dll_path)
        
        # 使用完整的种子响应数据作为种子列表
        seed_list = seed_response
        
        # 创建必要的数组和变量
        seed_ubyte_array = (c_ubyte * len(seed_list))()
        for i in range(len(seed_list)):
            seed_ubyte_array[i] = seed_list[i]
        
        key_ubyte_array = (c_ubyte * 16)()  # 增大数组大小，确保足够空间
        key_array_size = ctypes.c_byte()
        
        # 设置函数参数类型
        dll.GenerateKeyEx.argtypes = [
            POINTER(c_ubyte),  # 种子数组
            c_int,            # 种子数组长度
            c_int,            # 解锁级别
            c_char_p,         # 描述
            POINTER(c_ubyte),  # 密钥数组
            c_int,            # 密钥数组大小
            POINTER(c_byte)   # 实际密钥大小
        ]
        
        # 设置函数返回类型
        dll.GenerateKeyEx.restype = c_int
        
        # 调用DLL文件中的密钥生成函数
        description = b"description"  # 使用字节字符串
        result = dll.GenerateKeyEx(
            seed_ubyte_array, 
            len(seed_list), 
            unlock_level, 
            description, 
            key_ubyte_array, 
            16,  # 增大数组大小
            ctypes.pointer(key_array_size)
        )
        
        if result != 0:
            return {
                "success": False,
                "error": f"DLL函数调用失败，错误码: {result}"
            }
        
        # 提取生成的密钥
        key_list = list(key_ubyte_array[0:int(key_array_size.value)])
        
        # 将密钥转换为十六进制格式
        hex_key_list = [f"0x{byte:02x}" for byte in key_list]
        
        return {
            "success": True,
            "key": hex_key_list,
            "raw_key": key_list  # 保留原始十进制密钥，以便向后兼容
        }
        
    except Exception as e:
        import traceback
        return {
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }


if __name__ == "__main__":
    """
    作为独立脚本运行时，接收JSON格式的参数并返回JSON格式的结果
    示例调用：
    python seedkey_32bit_proxy.py '[{"seed_response": [0x67, 0x01, 0x10, 0x20, 0x30, 0x40], "unlock_level": 1}]'
    """
    try:
        # 检查命令行参数
        if len(sys.argv) < 2:
            print(json.dumps({
                "success": False,
                "error": "缺少参数"
            }))
            sys.exit(1)
        
        # 解析输入参数
        input_json = sys.argv[1]
        input_data = json.loads(input_json)
        
        # 验证输入数据格式
        if not isinstance(input_data, dict):
            print(json.dumps({
                "success": False,
                "error": "输入参数格式错误"
            }))
            sys.exit(1)
        
        # 调用密钥生成函数
        result = generate_key_from_seed(
            input_data.get("seed_response"),
            input_data.get("unlock_level", 1),
            input_data.get("dll_path", r'E:\workspace\01_ABS\03_N001\00-canoe\12-CDDDLL\Key_EQ100.dll')
        )
        
        # 输出JSON格式结果
        print(json.dumps(result))
        sys.exit(0)
        
    except Exception as e:
        print(json.dumps({
            "success": False,
            "error": f"代理脚本执行失败: {str(e)}"
        }))
        sys.exit(1)
