# 使用python调用DLL文件计算安全访问密钥
import ctypes
from ctypes import *
import os
import subprocess
import json
import sys
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
                print(f"DLL文件太小，不是有效的PE文件: {dll_path}")
                return None
            
            # 检查DOS签名
            if dos_header[:2] != b'MZ':
                print(f"不是有效的可执行文件（缺少MZ签名）: {dll_path}")
                return None
            
            # 获取PE头偏移量
            pe_offset = struct.unpack('<L', dos_header[60:64])[0]
            
            # 移动到PE头位置
            f.seek(pe_offset)
            
            # 读取PE签名
            pe_signature = f.read(4)
            if pe_signature != b'PE\x00\x00':
                print(f"不是有效的PE文件（缺少PE签名）: {dll_path}")
                return None
            
            # 读取机器类型（2字节）
            machine_type = struct.unpack('<H', f.read(2))[0]
            
            # 判断机器类型
            if machine_type == 0x014c:  # IMAGE_FILE_MACHINE_I386
                return 32
            elif machine_type == 0x8664:  # IMAGE_FILE_MACHINE_AMD64
                return 64
            else:
                print(f"未知的机器类型 ({machine_type}): {dll_path}")
                return None
    
    except Exception as e:
        print(f"判断DLL位数时发生错误: {str(e)}")
        return None


def generate_key_from_seed(seed_response, unlock_level=1, dll_path=r'E:\workspace\01_ABS\03_N001\00-canoe\12-CDDDLL\Key_EQ100.dll', proxy_python_path=r'C:\Program Files (x86)\Python39-32\python.exe'):
    """
    使用DLL文件从种子数据生成安全访问密钥
    
    参数:
        seed_response: 种子响应数据列表 (例如: [0x67, 0x01, 0x10, 0x20, 0x30, 0x40])
        unlock_level: 解锁级别，默认值为 1
        dll_path: DLL文件路径，默认值为 'E:\workspace\01_ABS\03_N001\00-canoe\12-CDDDLL\Key_EQ100.dll'
        proxy_python_path: 32位Python解释器路径，用于跨位数调用，默认值为 'C:\Program Files (x86)\Python39-32\python.exe'
    
    返回:
        list: 生成的密钥列表，如果调用失败返回None
    """
    try:
        # 检查DLL文件是否存在
        if not os.path.exists(dll_path):
            print(f"DLL文件不存在: {dll_path}")
            return None
        
        print(f"正在加载DLL文件: {dll_path}")
        python_bits = ctypes.sizeof(ctypes.c_void_p) * 8
        print(f"Python版本: {python_bits}位")
        
        # 检测DLL位数
        dll_bits = get_dll_bitness(dll_path)
        if dll_bits:
            print(f"DLL位数: {dll_bits}位")
        else:
            print("无法确定DLL位数")
        
        # 根据Python和DLL位数决定调用方式
        use_proxy = False
        
        if dll_bits:
            if python_bits == 64 and dll_bits == 32:
                print("检测到64位Python和32位DLL，正在使用32位Python代理调用...")
                use_proxy = True
            elif python_bits == 32 and dll_bits == 64:
                print(f"错误：当前Python是32位，但DLL是64位")
                print("解决方案：使用64位Python解释器或寻找32位版本的DLL")
                return None
            elif python_bits == dll_bits:
                print(f"Python和DLL都是{dll_bits}位，正在直接调用...")
            else:
                print(f"Python ({python_bits}位) 和 DLL ({dll_bits}位) 位数不匹配")
                return None
        else:
            # 如果无法确定DLL位数，对于64位Python仍然尝试使用代理
            if python_bits == 64:
                print("检测到64位Python，正在使用32位Python代理调用...")
                use_proxy = True
        
        # 如果需要使用代理调用
        if use_proxy:
            # 检查32位Python解释器是否存在
            if not os.path.exists(proxy_python_path):
                print(f"32位Python解释器不存在: {proxy_python_path}")
                print("请确保已安装32位Python并正确配置路径")
                return None
            
            # 获取当前脚本路径
            current_script_path = os.path.abspath(__file__)
            proxy_script_path = os.path.join(os.path.dirname(current_script_path), "seedkey_32bit_proxy.py")
            
            # 检查代理脚本是否存在
            if not os.path.exists(proxy_script_path):
                print(f"32位代理脚本不存在: {proxy_script_path}")
                return None
            
            # 准备输入参数
            input_data = {
                "seed_response": seed_response,
                "unlock_level": unlock_level,
                "dll_path": dll_path
            }
            input_json = json.dumps(input_data)
            
            # 调用32位Python代理
            try:
                result = subprocess.run(
                    [proxy_python_path, proxy_script_path, input_json],
                    capture_output=True,
                    text=True,
                    encoding='utf-8',
                    timeout=10
                )
                
                if result.returncode != 0:
                    print(f"32位Python代理调用失败，返回码: {result.returncode}")
                    print(f"错误输出: {result.stderr}")
                    return None
                
                # 解析代理返回结果
                proxy_result = json.loads(result.stdout)
                
                if proxy_result["success"]:
                    print("通过32位Python代理调用成功")
                    return proxy_result['key']
                else:
                    print(f"32位Python代理调用失败: {proxy_result.get('error', '未知错误')}")
                    if "traceback" in proxy_result:
                        print(f"错误堆栈: {proxy_result['traceback']}")
                    return None
                    
            except subprocess.TimeoutExpired:
                print("32位Python代理调用超时")
                return None
            except json.JSONDecodeError:
                print("32位Python代理返回的JSON格式错误")
                print(f"代理输出: {result.stdout}")
                return None
            except Exception as e:
                print(f"32位Python代理调用异常: {str(e)}")
                import traceback
                traceback.print_exc()
                return None
        
        try:
            # 尝试使用WinDLL加载（使用Windows调用约定）
            dll = ctypes.WinDLL(dll_path)
            print("DLL加载成功")
        except OSError as e:
            if "不是有效的 Win32 应用程序" in str(e):
                print(f"DLL加载失败: {e}")
                print("原因: DLL文件位数与Python解释器位数不匹配")
                if dll_bits:
                    print(f"当前Python是{python_bits}位，DLL是{dll_bits}位")
                else:
                    print(f"当前Python是{python_bits}位，DLL可能是{32 if python_bits == 64 else 64}位")
                print("解决方案: 使用与DLL文件位数相匹配的Python解释器")
            else:
                print(f"DLL加载失败: {e}")
            return None
        
        # 使用完整的种子响应数据作为种子列表
        seed_list = seed_response
        print(f"种子数据: {seed_list}")
        
        # 创建必要的数组和变量
        seed_ubyte_array = (c_ubyte * len(seed_list))()
        for i in range(len(seed_list)):
            seed_ubyte_array[i] = seed_list[i]
        
        key_ubyte_array = (c_ubyte * 16)()  # 增大数组大小，确保足够空间
        key_array_size = ctypes.c_byte()
        
        print(f"解锁级别: {unlock_level}")
        print(f"种子数组长度: {len(seed_list)}")
        
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
        
        print(f"函数调用结果: {result}")
        print(f"实际密钥大小: {key_array_size.value}")
        
        if result != 0:
            print(f"DLL函数调用失败，错误码: {result}")
            return None
        
        # 提取生成的密钥
        key_list = key_ubyte_array[0:int(key_array_size.value)]
        
        # 将密钥转换为十六进制格式
        hex_key_list = [f"0x{byte:02x}" for byte in key_list]
        return hex_key_list
        
    except Exception as e:
        print(f"DLL调用失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return None


# 示例使用
if __name__ == "__main__":
    # 模拟服务器返回的种子响应数据
    seed_response = [0x6f, 0x3b, 0xf2, 0xf4]
    unlock_level = 5  # 解锁级别
    
    # 调用函数生成密钥
    key = generate_key_from_seed(seed_response, unlock_level)
    
    if key:
        print(f"生成的密钥: {key}")
    else:
        print("密钥生成失败")