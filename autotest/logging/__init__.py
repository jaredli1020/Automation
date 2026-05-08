"""日志系统

- 按天轮转（DailyRotatingFileHandler）
- 自动清理过期日志（LogCleaner，默认保留 15 天）
- 单例 LoggerManager

业务模块通过 get_logger(__name__) 获取日志实例。
"""

from .logger import (
    LoggerManager,
    LogCleaner,
    DailyRotatingFileHandler,
    setup_logging,
    get_logger,
    cleanup_old_logs,
)

__all__ = [
    "LoggerManager",
    "LogCleaner",
    "DailyRotatingFileHandler",
    "setup_logging",
    "get_logger",
    "cleanup_old_logs",
]
