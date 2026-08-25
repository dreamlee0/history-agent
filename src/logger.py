"""
轻量日志模块 - 统一日志配置，替代散落的 print

为什么需要：print 无法区分级别/时间、不方便在日志系统中按模块过滤。
这里提供统一的 get_logger()，各模块获取 logger 后用于记录进度与错误，
保留默认输出到 stdout（与 print 行为一致，不影响 Streamlit 展示）。
"""
import logging
import sys

_configured = False


def get_logger(name: str = "history_agent") -> logging.Logger:
    """获取统一配置的 logger（首次调用时初始化根配置）"""
    global _configured
    if not _configured:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            handlers=[logging.StreamHandler(sys.stdout)],
        )
        _configured = True
    return logging.getLogger(name)
