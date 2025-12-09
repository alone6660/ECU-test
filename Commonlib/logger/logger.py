# -*- coding: utf-8 -*-
import logging.config
import os
import sys
import time

# 添加项目根目录到Python路径
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(project_root)

from .log_config import LOGGING_CONFIG


def setup_logging():
    """
    初始化日志系统
    """
    # 应用配置
    logging.config.dictConfig(LOGGING_CONFIG)

    # 获取应用日志记录器
    logger = logging.getLogger('app')
    logger.info("日志系统初始化完成")

    return logger


def get_module_logger(module_name):
    """
    获取模块特定的日志记录器
    """
    return logging.getLogger(f'app.{module_name}')


def get_database_logger():
    """
    获取数据库日志记录器
    """
    return logging.getLogger('database')


def get_api_logger():
    """
    获取API日志记录器
    """
    return logging.getLogger('api')





if __name__ == '__main__':
    # 初始化日志系统
    logger = setup_logging()

    # 获取不同模块的日志记录器
    db_logger = get_database_logger()
    api_logger = get_api_logger()
    service_logger = get_module_logger('service')

    # 显示不同级别的日志记录
    logger.debug("这是调试信息 - 通常用于开发阶段")
    logger.info("操作执行成功 - 一般信息记录")
    logger.warning("内存空间不足 - 需要注意警告")
    db_logger.info("开始数据库操作")
    # 模拟业务流程
    try:
        db_logger.info("开始数据库查询")
        # 模拟数据库查询
        time.sleep(0.1)

        api_logger.debug("API请求参数: {'user': 'test'}")

        # 模拟一个错误
        raise ValueError("模拟业务流程错误")

    except Exception as e:
        logger.error(f"业务处理失败: {e}", exc_info=True)



    logger.info("程序执行结束")
