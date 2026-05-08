"""统一日志模块 - 按天轮转 + 自动清理过期日志"""

import os
import sys
import logging
import threading
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from typing import Optional
from datetime import datetime, timedelta


class LogCleaner:
    """日志清理器 - 定时清理过期日志文件"""

    def __init__(self, log_dir: Path, retention_days: int = 15, log_pattern: str = "*.log*"):
        self.log_dir = log_dir
        self.retention_days = retention_days
        self.log_pattern = log_pattern
        self._timer: Optional[threading.Timer] = None
        self._stop_event = threading.Event()

    def clean_old_logs(self) -> int:
        if not self.log_dir or not self.log_dir.exists():
            return 0

        deleted_count = 0
        cutoff_time = datetime.now() - timedelta(days=self.retention_days)

        for log_file in self.log_dir.glob(self.log_pattern):
            try:
                file_mtime = datetime.fromtimestamp(log_file.stat().st_mtime)
                if file_mtime < cutoff_time:
                    log_file.unlink()
                    deleted_count += 1
                    print(f"已删除过期日志: {log_file.name} (修改时间: {file_mtime.strftime('%Y-%m-%d')})")
            except Exception as e:
                print(f"删除日志文件失败 {log_file}: {e}")

        return deleted_count

    def start_scheduled_cleanup(self, interval_hours: int = 24):
        if self._stop_event.is_set():
            return

        self.clean_old_logs()
        self._timer = threading.Timer(
            interval_hours * 3600,
            self.start_scheduled_cleanup,
            args=[interval_hours],
        )
        self._timer.daemon = True
        self._timer.start()

    def stop_scheduled_cleanup(self):
        self._stop_event.set()
        if self._timer:
            self._timer.cancel()
            self._timer = None


class DailyRotatingFileHandler(TimedRotatingFileHandler):
    """按天轮转的日志处理器，文件名包含日期"""

    def __init__(self, log_dir: Path, filename: str = "autotest",
                 retention_days: int = 15, encoding: str = "utf-8"):
        self.log_dir = log_dir
        self.base_filename = filename
        self.retention_days = retention_days

        log_file = self._get_log_filename()
        super().__init__(
            log_file,
            when="midnight",
            interval=1,
            backupCount=retention_days,
            encoding=encoding,
        )
        self.suffix = "%Y-%m-%d"
        self.extMatch = r"^\d{4}-\d{2}-\d{2}$"

    def _get_log_filename(self) -> str:
        today = datetime.now().strftime("%Y-%m-%d")
        return str(self.log_dir / f"{self.base_filename}_{today}.log")

    def doRollover(self):
        if self.stream:
            self.stream.close()
            self.stream = None

        self.baseFilename = self._get_log_filename()
        self.stream = self._open()
        self._cleanup_old_logs()

    def _cleanup_old_logs(self):
        cutoff_time = datetime.now() - timedelta(days=self.retention_days)
        for log_file in self.log_dir.glob(f"{self.base_filename}_*.log"):
            try:
                date_str = log_file.stem.replace(f"{self.base_filename}_", "")
                file_date = datetime.strptime(date_str, "%Y-%m-%d")
                if file_date < cutoff_time:
                    log_file.unlink()
            except (ValueError, OSError):
                pass


class LoggerManager:
    """日志管理器 - 单例模式"""

    _instance: Optional["LoggerManager"] = None
    _initialized: bool = False

    LEVEL_MAP = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL,
    }

    DEFAULT_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(filename)s:%(lineno)d | %(message)s"
    DEFAULT_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
    DEFAULT_LOG_DIR = "logs"
    DEFAULT_LOG_LEVEL = "INFO"
    DEFAULT_RETENTION_DAYS = 15

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if LoggerManager._initialized:
            return

        self._loggers: dict = {}
        self._log_dir: Optional[Path] = None
        self._console_handler: Optional[logging.Handler] = None
        self._file_handler: Optional[logging.Handler] = None
        self._log_level: int = logging.INFO
        self._formatter: Optional[logging.Formatter] = None
        self._log_cleaner: Optional[LogCleaner] = None
        self._retention_days: int = self.DEFAULT_RETENTION_DAYS

        LoggerManager._initialized = True

    def setup(self, log_dir: str = None, log_level: str = None,
              log_format: str = None, date_format: str = None,
              console_output: bool = True, file_output: bool = True,
              retention_days: int = None, log_filename: str = None,
              auto_cleanup: bool = True) -> "LoggerManager":
        level_str = log_level or os.getenv("LOG_LEVEL", self.DEFAULT_LOG_LEVEL)
        self._log_level = self.LEVEL_MAP.get(level_str.upper(), logging.INFO)
        self._retention_days = retention_days or int(os.getenv("LOG_RETENTION_DAYS", self.DEFAULT_RETENTION_DAYS))

        fmt = log_format or os.getenv("LOG_FORMAT", self.DEFAULT_FORMAT)
        date_fmt = date_format or self.DEFAULT_DATE_FORMAT
        self._formatter = logging.Formatter(fmt, datefmt=date_fmt)

        if console_output:
            self._setup_console_handler()

        if file_output:
            log_dir_path = log_dir or os.getenv("LOG_DIR", self.DEFAULT_LOG_DIR)
            self._log_dir = Path(log_dir_path)
            self._log_dir.mkdir(parents=True, exist_ok=True)
            self._setup_file_handler(retention_days=self._retention_days, log_filename=log_filename)
            if auto_cleanup:
                self._setup_log_cleaner()

        return self

    def _setup_console_handler(self):
        if self._console_handler is None:
            self._console_handler = logging.StreamHandler(sys.stdout)
            self._console_handler.setLevel(self._log_level)
            self._console_handler.setFormatter(self._formatter)

    def _setup_file_handler(self, retention_days: int, log_filename: str = None):
        if self._log_dir is None:
            return
        filename = log_filename or "autotest"
        self._file_handler = DailyRotatingFileHandler(
            log_dir=self._log_dir,
            filename=filename,
            retention_days=retention_days,
        )
        self._file_handler.setLevel(self._log_level)
        self._file_handler.setFormatter(self._formatter)

    def _setup_log_cleaner(self):
        if self._log_dir is None:
            return
        self._log_cleaner = LogCleaner(
            log_dir=self._log_dir,
            retention_days=self._retention_days,
        )
        self._log_cleaner.start_scheduled_cleanup(interval_hours=24)

    def get_logger(self, name: str = None) -> logging.Logger:
        logger_name = name or "autotest"
        if logger_name in self._loggers:
            return self._loggers[logger_name]

        logger = logging.getLogger(logger_name)
        logger.setLevel(self._log_level)
        logger.propagate = False
        logger.handlers.clear()

        if self._console_handler:
            logger.addHandler(self._console_handler)
        if self._file_handler:
            logger.addHandler(self._file_handler)

        if not logger.handlers:
            handler = logging.StreamHandler(sys.stdout)
            handler.setLevel(self._log_level)
            handler.setFormatter(self._formatter or logging.Formatter(self.DEFAULT_FORMAT))
            logger.addHandler(handler)

        self._loggers[logger_name] = logger
        return logger

    def set_level(self, level: str):
        self._log_level = self.LEVEL_MAP.get(level.upper(), logging.INFO)
        for logger in self._loggers.values():
            logger.setLevel(self._log_level)
        if self._console_handler:
            self._console_handler.setLevel(self._log_level)
        if self._file_handler:
            self._file_handler.setLevel(self._log_level)

    def cleanup_old_logs(self) -> int:
        if self._log_cleaner:
            return self._log_cleaner.clean_old_logs()
        return 0

    def shutdown(self):
        if self._log_cleaner:
            self._log_cleaner.stop_scheduled_cleanup()
        for logger in self._loggers.values():
            for handler in logger.handlers[:]:
                handler.close()
                logger.removeHandler(handler)
        self._loggers.clear()


_manager = LoggerManager()


def setup_logging(log_dir: str = None, log_level: str = None,
                  console_output: bool = True, file_output: bool = True,
                  retention_days: int = None, **kwargs) -> LoggerManager:
    """配置日志系统（便捷函数）"""
    return _manager.setup(
        log_dir=log_dir,
        log_level=log_level,
        console_output=console_output,
        file_output=file_output,
        retention_days=retention_days,
        **kwargs,
    )


def get_logger(name: str = None) -> logging.Logger:
    """获取日志记录器（便捷函数）"""
    return _manager.get_logger(name)


def cleanup_old_logs() -> int:
    """手动清理过期日志（便捷函数）"""
    return _manager.cleanup_old_logs()
