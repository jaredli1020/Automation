"""demo 业务测试 fixtures"""

import pytest
from demo.config.settings import Settings
from autotest.api import APIClient, AuthManager


@pytest.fixture(scope="session")
def settings():
    """业务 Settings 类"""
    return Settings


@pytest.fixture(scope="session")
def auth_token(settings):
    """登录并缓存 token"""
    return AuthManager.login(settings_class=settings)


@pytest.fixture(scope="session")
def api_client(settings, auth_token):
    """已登录的 API 客户端"""
    client = APIClient.from_settings(settings, token=auth_token)
    yield client
    client.close()
