"""登录认证接口测试示例"""

import pytest


@pytest.mark.api
def test_login_success(api_client):
    """登录成功 - 获取 token 后客户端可正常调用接口"""
    assert api_client.session.headers.get("token"), "token 未设置"
