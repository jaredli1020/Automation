"""基础配置类 - 所有业务模块的 Settings 基类

每个业务模块应继承 BaseSettings，覆盖 ENVS 字典并调用 load_env() 加载
环境配置。框架通过参数化而非硬编码访问所有字段。
"""

import os
from pathlib import Path


class classproperty:
    """类属性描述符，支持在类上直接访问动态属性"""
    def __init__(self, func):
        self.fget = func

    def __get__(self, obj, owner):
        return self.fget(owner)


# 默认项目根目录 - 业务项目可在自己的 Settings 中覆盖
DEFAULT_PROJECT_ROOT = Path.cwd()


class BaseSettings:
    """所有业务模块配置的基类"""

    # 当前环境
    ENV = os.environ.get("ENV", "prod")

    # 超时时间（毫秒）
    DEFAULT_TIMEOUT = 10000
    LONG_TIMEOUT = 30000
    SHORT_TIMEOUT = 3000

    # 项目路径（由调用方传入或继承类覆盖）
    PROJECT_ROOT = Path(os.environ.get("PROJECT_ROOT", DEFAULT_PROJECT_ROOT))
    SCREENSHOTS_DIR = PROJECT_ROOT / "screenshots"
    REPORTS_DIR = PROJECT_ROOT / "reports"
    LOGS_DIR = PROJECT_ROOT / "logs"

    # 测试账号（各业务覆盖）
    TEST_ACCOUNT = ""
    TEST_PASSWORD = ""

    # API 测试配置（各业务覆盖）
    API_BASE_URL = ""
    API_HOST_IP = ""
    API_TIMEOUT = 30
    API_LOGIN_PATH = ""

    # 飞书通知配置
    FEISHU_WEBHOOK_URL = os.environ.get("FEISHU_WEBHOOK_URL", "")
    FEISHU_NOTIFY_ENABLED = os.environ.get("FEISHU_NOTIFY_ENABLED", "true").lower() == "true"

    # 报告访问配置
    REPORT_BASE_URL = os.environ.get("REPORT_BASE_URL", "http://localhost:8000")

    # 环境配置（子类必须定义 ENVS 字典）
    ENVS: dict = {}

    @classmethod
    def load_env(cls, env_name: str = None):
        """加载指定环境配置，覆盖类变量"""
        env_name = env_name or cls.ENV
        if not cls.ENVS:
            return
        if env_name not in cls.ENVS:
            raise ValueError(f"未知环境: {env_name}，可选: {list(cls.ENVS.keys())}")
        cls.ENV = env_name
        env_config = cls.ENVS[env_name]
        cls.API_BASE_URL = env_config.get("API_BASE_URL", cls.API_BASE_URL)
        cls.API_HOST_IP = env_config.get("API_HOST_IP", "")
        cls.TEST_ACCOUNT = env_config.get("TEST_ACCOUNT", cls.TEST_ACCOUNT)
        cls.TEST_PASSWORD = env_config.get("TEST_PASSWORD", cls.TEST_PASSWORD)
        cls.FEISHU_WEBHOOK_URL = env_config.get("FEISHU_WEBHOOK_URL", cls.FEISHU_WEBHOOK_URL)
        print(f"[环境] 已切换到 {env_name} 环境 | API: {cls.API_BASE_URL} | 账号: {cls.TEST_ACCOUNT}"
              + (f" | IP: {cls.API_HOST_IP}" if cls.API_HOST_IP else ""))

    @classmethod
    def ensure_dirs(cls):
        """确保输出目录存在"""
        cls.SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
        cls.REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        cls.LOGS_DIR.mkdir(parents=True, exist_ok=True)
