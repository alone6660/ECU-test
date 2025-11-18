import pytest
import sys
import logging
from datetime import datetime

from Testsuit.test_releasetest.env import logger

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')


# === 引导钩子函数 ===
def pytest_load_initial_conftests(early_config, args, parser):
    """引导钩子：加载初始conftest文件"""
    logger.info("当前运行: pytest_load_initial_conftests")
    logger.info("加载conftest.py文件")

def pytest_cmdline_parse(args, pluginmanager):
    """引导钩子：解析命令行参数"""
    logger.info("当前运行: pytest_cmdline_parse")
    logger.info(f"命令行参数: {args}")

def pytest_cmdline_main(config):
    """引导钩子：执行主命令"""
    logger.info("当前运行: pytest_cmdline_main")
    logger.info("调用命令解析钩子和执行runtest_mainloop")

# === 初始化钩子函数 ===
def pytest_configure(config):
    """初始化钩子：pytest配置"""
    logger.info("当前运行: pytest_configure")
    config.option.verbose = True
    logger.info("pytest配置完成 - 启用详细模式")

# === 测试会话钩子函数 ===
def pytest_sessionstart(session):
    """测试会话开始"""
    logger.info("当前运行: pytest_sessionstart")
    logger.info("=== 测试会话开始 ===")
    session.start_time = datetime.now()

def pytest_sessionfinish(session, exitstatus):
    """测试会话结束"""
    logger.info("当前运行: pytest_sessionfinish")
    end_time = datetime.now()
    duration = end_time - session.start_time
    logger.info(f"=== 测试会话结束，总耗时: {duration} ===")

def pytest_unconfigure(config):
    """pytest卸载配置"""
    logger.info("当前运行: pytest_unconfigure")
    logger.info("清理全局资源")

# === 测试收集钩子函数 ===
def pytest_collection(session):
    """测试收集开始"""
    logger.info("当前运行: pytest_collection")
    logger.info("开始收集测试用例")

def pytest_collection_modifyitems(config, items):
    """修改收集的测试用例"""
    logger.info("当前运行: pytest_collection_modifyitems")
    logger.info(f"共收集到 {len(items)} 个测试用例")

    # 为所有测试用例添加自定义标记
    for item in items:
        if not any(marker for marker in item.own_markers if marker.name == "slow"):
            item.add_marker(pytest.mark.fast)

# === 测试执行钩子函数 ===
@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_protocol(item, nextitem):
    """测试执行协议"""
    logger.info("当前运行: pytest_runtest_protocol")
    result = yield
    logger.info("结束运行: pytest_runtest_protocol")

@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_setup(item):
    """测试用例setup阶段"""
    logger.info("当前运行: pytest_runtest_setup")
    logger.info('执行setup模块')
    result = yield
    logger.info("结束运行: pytest_runtest_setup")

@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_call(item):
    """测试用例调用"""
    logger.info("当前运行: pytest_runtest_call")
    result = yield
    logger.info("结束运行: pytest_runtest_call")

@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_teardown(item):
    """测试用例teardown阶段"""
    logger.info("当前运行: pytest_runtest_teardown")
    logger.info('执行teardown模块')
    result = yield
    logger.info("结束运行: pytest_runtest_teardown")

def pytest_runtest_logreport(report):
    """测试报告日志"""
    if report.when == "call":
        logger.info(f"测试执行结果: {report.outcome}")

# === Fixture相关钩子函数 ===
@pytest.hookimpl(hookwrapper=True)
def pytest_fixture_setup(fixturedef, request):
    """fixture设置"""
    logger.info("当前运行: pytest_fixture_setup")
    logger.info('开始安装fixture模块-' + str(request.fixturename))
    result = yield
    logger.info("结束运行: pytest_fixture_setup")

@pytest.hookimpl(hookwrapper=True)
def pytest_fixture_post_finalizer(fixturedef, request):
    """fixture卸载"""
    logger.info("当前运行: pytest_fixture_post_finalizer")
    logger.info('开始卸载fixture模块-' + str(request.fixturename))
    result = yield
    logger.info("结束运行: pytest_fixture_post_finalizer")

# === Fixture定义 ===
@pytest.fixture(scope="session", autouse=True)
def global_session_setup():
    """全局会话级别fixture"""
    logger.info("\n=== 全局会话fixture开始 ===")
    yield
    logger.info("\n=== 全局会话fixture结束 ===")

@pytest.fixture(scope="class")
def class_fixture():
    """类级别fixture"""
    logger.info("\n初始化 class_fixture")
    return "class fixture data"

@pytest.fixture(scope="function", autouse=True)
def function_setup():
    """函数级别fixture"""
    logger.info("\n>>> 测试函数fixture初始化")
    yield
    logger.info("\n>>> 测试函数fixture清理")
