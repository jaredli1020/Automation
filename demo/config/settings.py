"""demo 业务 Settings - 继承 BaseSettings，定义 ENVS 和业务专属字段"""

from autotest.config import BaseSettings
from .envs import ENVS


class Settings(BaseSettings):
    """demo 业务配置"""

    # 环境字典（prod / test 等）
    ENVS = ENVS

    # API 登录接口路径（相对 API_BASE_URL）
    API_LOGIN_PATH = "/api/user/login"

    # 业务超时（可覆盖基类默认值）
    DEFAULT_TIMEOUT = 10000
    LONG_TIMEOUT = 30000
    SHORT_TIMEOUT = 3000
