"""API 响应断言工具"""

from .client import APIResponse


def assert_success(resp: APIResponse, msg: str = ""):
    """断言请求成功（HTTP 200 + 业务码 0）"""
    prefix = f"{msg}: " if msg else ""
    assert resp.status_code == 200, f"{prefix}HTTP 状态码异常: {resp.status_code}"
    assert resp.code == 0, f"{prefix}业务码异常: {resp.code}, 消息: {resp.message}"


def assert_status(resp: APIResponse, expected: int):
    """断言 HTTP 状态码"""
    assert resp.status_code == expected, (
        f"期望状态码 {expected}，实际 {resp.status_code}"
    )


def assert_json_has_keys(resp: APIResponse, keys: list[str]):
    """断言响应 data 中包含指定字段"""
    data = resp.data
    assert data is not None, "响应 data 为空"
    missing = [k for k in keys if k not in data]
    assert not missing, f"响应缺少字段: {missing}"


def assert_list_not_empty(resp: APIResponse, list_key: str = None):
    """断言响应中的列表不为空"""
    data = resp.data
    if list_key:
        data = data.get(list_key, [])
    assert isinstance(data, list) and len(data) > 0, "列表为空"
