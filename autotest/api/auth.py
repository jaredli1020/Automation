"""认证管理 - 参数化版本"""

import hashlib
from typing import Optional
from .client import APIClient


def md5(text: str) -> str:
    """MD5 加密"""
    return hashlib.md5(text.encode()).hexdigest()


class AuthManager:
    """管理 API 认证，获取并缓存 token。

    支持两种使用方式：
    1. 传入 settings_class，自动从中读取账号/密码/登录路径/API 配置；
    2. 直接传入 email/password/login_path + 手动构造 APIClient。
    """

    _token_cache: dict[str, str] = {}

    @classmethod
    def login(cls, email: str = None, password: str = None,
              settings_class=None, login_path: str = None,
              password_hash: bool = True,
              token_key: str = "token") -> str:
        """登录并返回 token

        Args:
            email: 登录账号（邮箱/手机号/用户名），默认从 settings_class.TEST_ACCOUNT 读取
            password: 登录密码，默认从 settings_class.TEST_PASSWORD 读取
            settings_class: Settings 类，提供默认账号/密码/API 配置
            login_path: 登录接口路径，默认从 settings_class.API_LOGIN_PATH 读取
            password_hash: 是否 MD5 加密密码（默认 True，按需关闭）
            token_key: 响应 data 中 token 字段的键名（默认 "token"）
        """
        if settings_class:
            email = email or settings_class.TEST_ACCOUNT
            password = password or settings_class.TEST_PASSWORD
            login_path = login_path or getattr(settings_class, "API_LOGIN_PATH", "")

        if not email or not password or not login_path:
            raise ValueError("必须提供 email、password 和 login_path，或传入 settings_class")

        cache_key = f"{email}@{login_path}"
        if cache_key in cls._token_cache:
            return cls._token_cache[cache_key]

        if settings_class:
            client = APIClient.from_settings(settings_class)
        else:
            client = APIClient()

        payload = {
            "email": email,
            "password": md5(password) if password_hash else password,
        }
        resp = client.post(login_path, json=payload)

        if not resp.ok:
            raise RuntimeError(f"登录失败: {resp.message}")

        token = resp.data.get(token_key, "") if resp.data else ""
        if not token:
            raise RuntimeError(f"登录响应未找到 token 字段: {token_key}")
        cls._token_cache[cache_key] = token
        return token

    @classmethod
    def clear_cache(cls, email: Optional[str] = None):
        """清理 token 缓存。传入 email 只清对应账号，不传则清全部"""
        if email is None:
            cls._token_cache.clear()
        else:
            cls._token_cache = {
                k: v for k, v in cls._token_cache.items() if not k.startswith(f"{email}@")
            }
