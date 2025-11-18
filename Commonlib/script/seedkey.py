def generic_algorithm(seed, security_constant):
    """
    SAIC Security Algorithm
    对应 C 代码中的 Generic_Algorithm 函数
    """
    w_last_seed = seed

    # 计算 temp 值
    temp_val = (((security_constant & 0x00000800) >> 10) |
                ((security_constant & 0x00200000) >> 21))

    # 根据 temp_val 选择不同的字节
    if temp_val == 0:
        w_temp = (seed & 0xFF000000) >> 24
    elif temp_val == 1:
        w_temp = (seed & 0x00FF0000) >> 16
    elif temp_val == 2:
        w_temp = (seed & 0x0000FF00) >> 8
    elif temp_val == 3:
        w_temp = seed & 0x000000FF
    else:
        w_temp = 0

    # 计算 SB1, SB2, SB3
    SB1 = (security_constant & 0x000003FC) >> 2
    SB2 = ((security_constant & 0x7F800000) >> 23) ^ 0xA5
    SB3 = ((security_constant & 0x001FE000) >> 13) ^ 0x5A

    # 计算迭代次数
    iterations = ((w_temp ^ SB1) & SB2) + SB3

    # 执行迭代
    for jj in range(iterations):
        w_temp = ((w_last_seed & 0x40000000) // 0x40000000) ^ \
                 ((w_last_seed & 0x01000000) // 0x01000000) ^ \
                 ((w_last_seed & 0x1000) // 0x1000) ^ \
                 ((w_last_seed & 0x04) // 0x04)

        w_ls_bit = w_temp & 0x00000001
        w_last_seed = (w_last_seed << 1) & 0xFFFFFFFF
        w_top_31_bits = w_last_seed & 0xFFFFFFFE
        w_last_seed = w_top_31_bits | w_ls_bit

    # 根据 security_constant 的最低位决定是否交换字节
    if (security_constant & 0x00000001) != 0:
        w_top_31_bits = ((w_last_seed & 0x00FF0000) >> 16) | \
                        ((w_last_seed & 0xFF000000) >> 8) | \
                        ((w_last_seed & 0x000000FF) << 8) | \
                        ((w_last_seed & 0x0000FF00) << 16)
    else:
        w_top_31_bits = w_last_seed

    # 与安全常量异或
    w_top_31_bits = w_top_31_bits ^ security_constant

    return w_top_31_bits & 0xFFFFFFFF


def croleft(c, b):
    """循环左移"""
    left = (c << b) & 0xFFFFFFFF
    right = c >> (32 - b)
    return (left | right) & 0xFFFFFFFF


def croshortright(c, b):
    """循环右移 (16位)"""
    right = c >> b
    left = (c << (16 - b)) & 0xFFFF
    return (left | right) & 0xFFFF


def mulu32(val1, val2):
    """32位乘法运算"""
    x = (val1 & NC_UDS_KEYMASK) | ((~val1) & val2)
    y = ((croleft(val1, 1)) & (croleft(val2, 14))) | \
        ((croleft(NC_UDS_KEYMASK, 21)) & (~(croleft(val1, 30))))
    z = (croleft(val1, 17)) ^ (croleft(val2, 4)) ^ (croleft(NC_UDS_KEYMASK, 11))
    p = x ^ y ^ z
    return p & 0xFFFFFFFF


def uds_calc_key(seed):
    """
    SGMW Security Algorithm
    对应 C 代码中的 uds_calc_key 函数
    """
    # 常量定义
    NC_DEFAULT_SEED = 0xA548FD85
    global NC_UDS_KEYMASK
    NC_UDS_KEYMASK = 0x561A48B2

    nc_uds_keymul = [
        0x7678, 0x9130, 0xD753, 0x750F, 0x72CB, 0x55F7, 0x13DA, 0x786B,
        0x372A, 0x4932, 0x0E7C, 0x3687, 0x3261, 0xA82C, 0x8935, 0xD00C,
        0x1995, 0x4311, 0xB854, 0x0D8D, 0x9863, 0x1A21, 0xF753, 0xD6D3,
        0xB15D, 0x7F3D, 0x6821, 0x791C, 0x26C5, 0x2E37, 0x0E69, 0x64A0
    ]

    if seed == 0:
        seed = NC_DEFAULT_SEED

    index = 0x5D39
    temp_mask = 0x80000000

    # 主要计算循环
    while temp_mask:
        if temp_mask & seed:
            index = croshortright(index, 1)
            if temp_mask & NC_UDS_KEYMASK:
                index ^= 0x74C9
        temp_mask >>= 1

    # 计算 mult1 和 mult2
    mult1 = nc_uds_keymul[(index >> 2) & 0x1F] ^ index
    mult2 = nc_uds_keymul[(index >> 8) & 0x1F] ^ index

    # 组合并计算最终结果
    temp = ((mult1 & 0xFFFF) << 16) | (mult2 & 0xFFFF)
    result = mulu32(seed, temp)

    return result & 0xFFFFFFFF


def seed_to_key_saic(seed_bytes, security_constant=0x3AD298CA):
    """
    使用 SAIC 算法将种子转换为密钥
    seed_bytes: 4字节的种子 (list of 4 bytes)
    security_constant: 安全常量，默认为 0x3AD298CA
    """
    seed = (seed_bytes[0] << 24) | (seed_bytes[1] << 16) | (seed_bytes[2] << 8) | seed_bytes[3]
    key = generic_algorithm(seed, security_constant)

    return [
        (key >> 24) & 0xFF,
        (key >> 16) & 0xFF,
        (key >> 8) & 0xFF,
        key & 0xFF
    ]
def extract_last_four_hex(hex_string):
    """从十六进制字符串中提取后四个字节"""
    hex_list = hex_string.replace('0x', '').replace(',', ' ').split()
    return [int(x, 16) for x in hex_list[-4:]]


def seed_to_key_sgmw(seed_bytes):
    """
    使用 SGMW 算法将种子转换为密钥
    seed_bytes: 4字节的种子 (list of 4 bytes)
    """
    seed = (seed_bytes[0] << 24) | (seed_bytes[1] << 16) | (seed_bytes[2] << 8) | seed_bytes[3]
    key = uds_calc_key(seed)

    return [
        (key >> 24) & 0xFF,
        (key >> 16) & 0xFF,
        (key >> 8) & 0xFF,
        key & 0xFF
    ]


# 全局变量
NC_UDS_KEYMASK = 0x561A48B2


def seed_to_key_sgmw_str(seed_str):
    """
    使用 SGMW 算法将种子字符串转换为密钥字符串
    seed_str: 种子字符串，如 "57 DB E8 EC" 或 "57DBE8EC"
    return: 密钥字符串，如 "12 34 56 78"
    """
    # 清理输入字符串并转换为字节列表
    seed_clean = seed_str.replace(' ', '').replace('0x', '').upper()

    # 确保是4字节（8个十六进制字符）
    if len(seed_clean) != 8:
        raise ValueError("种子必须是4字节（8个十六进制字符）")

    # 将字符串转换为4个字节
    seed_bytes = [
        int(seed_clean[0:2], 16),
        int(seed_clean[2:4], 16),
        int(seed_clean[4:6], 16),
        int(seed_clean[6:8], 16)
    ]

    # 计算密钥
    seed = (seed_bytes[0] << 24) | (seed_bytes[1] << 16) | (seed_bytes[2] << 8) | seed_bytes[3]
    key = uds_calc_key(seed)

    # 将密钥转换为十六进制字符串
    key_bytes = [
        (key >> 24) & 0xFF,
        (key >> 16) & 0xFF,
        (key >> 8) & 0xFF,
        key & 0xFF
    ]

    # 格式化为字符串
    key_str = ' '.join([f"{byte:02X}" for byte in key_bytes])

    return key_str
# 测试示例
if __name__ == "__main__":
    key = seed_to_key_sgmw_str("6f 3b f2 f4")
    print(key)

    # 示例种子
    # test_seed = [0x6F, 0x3B, 0xF2, 0xF4]
    #
    # print("输入种子:", [hex(x) for x in test_seed])
    #
    # # 使用 SAIC 算法
    # key_saic = seed_to_key_saic(test_seed)
    # print("SAIC 算法密钥:", [hex(x) for x in key_saic])
    #
    # # 使用 SGMW 算法
    # key_sgmw = seed_to_key_sgmw(test_seed)
    # print("SGMW 算法密钥:", [hex(x) for x in key_sgmw])
    #
    # # 测试 C 代码中提到的特定种子
    # specific_seed = [0x00, 0x00, 0x1F, 0x8F]  # 0x00001F8F
    # print("\n特定种子测试:", [hex(x) for x in specific_seed])
    #
    # key_saic_specific = seed_to_key_saic(specific_seed)
    # print("SAIC 特定种子密钥:", [hex(x) for x in key_saic_specific])