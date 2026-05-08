"""通用 API 测试框架"""

from .client import APIClient, APIResponse, get_request_log, clear_request_log
from .auth import AuthManager
from .assertions import (
    assert_success,
    assert_status,
    assert_json_has_keys,
    assert_list_not_empty,
)

__all__ = [
    "APIClient",
    "APIResponse",
    "AuthManager",
    "assert_success",
    "assert_status",
    "assert_json_has_keys",
    "assert_list_not_empty",
    "get_request_log",
    "clear_request_log",
]
