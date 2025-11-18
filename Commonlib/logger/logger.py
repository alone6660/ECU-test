import logging.config
import os
import time
from pathlib import Path

from Commonlib.logger.log_config import LOGGING_CONFIG


def setup_logging():
    """
    初始化日志系统
    """
    # 确保日志目录存在
    log_dir = 'logs'
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
        print(f"创建日志目录: {log_dir}")

    # 更新文件路径
    LOGGING_CONFIG['handlers']['file_handler']['filename'] = os.path.join(log_dir, 'app.log')
    LOGGING_CONFIG['handlers']['error_handler']['filename'] = os.path.join(log_dir, 'error.log')

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

    # 演示不同级别的日志记录
    logger.debug("这是调试信息 - 通常用于开发阶段")
    logger.info("程序启动成功 - 一般信息记录")
    logger.warning("磁盘空间不足警告 - 需要注意的情况")
    db_logger.info("开始数据库操作")
    # 模拟业务逻辑
    try:
        db_logger.info("开始数据库操作")
        # 模拟数据库操作
        time.sleep(0.1)

        api_logger.debug("API请求参数: {'user': 'test'}")

        # 模拟一个错误
        raise ValueError("模拟的业务逻辑错误")

    except Exception as e:
        logger.error(f"业务处理失败: {e}", exc_info=True)



    logger.info("程序执行完成")
