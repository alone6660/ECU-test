# -*- coding: utf-8 -*-


def write_string_to_txt(content, file_name="output.txt"):
    """
    写入字符串到当前目录下的txt文件
    :param content: 要写入的字符串内容
    :param file_name: 文件名，默认为output.txt
    """
    try:
        with open(file_name, 'a', encoding='utf-8') as file:
            file.write(content + '\n')  # 追加换行符
        print(f"内容已成功追加到文件: {file_name}")
    except Exception as e:
        print(f"追加内容时出错: {e}")
