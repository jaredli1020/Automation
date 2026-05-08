"""API 客户端基类 - 参数化构造，支持多业务模块复用"""

import json as json_lib
import threading
import requests
from urllib.parse import urlparse
from typing import Optional
from requests.adapters import HTTPAdapter


# ==================== 请求记录器（thread-local） ====================
_request_log = threading.local()
_MAX_RESPONSE_LEN = 2000


def get_request_log() -> list:
    """获取当前线程的请求记录"""
    if not hasattr(_request_log, "records"):
        _request_log.records = []
    return _request_log.records


def clear_request_log():
    """清空当前线程的请求记录"""
    _request_log.records = []


def _truncate_json(data, max_len=_MAX_RESPONSE_LEN) -> str:
    try:
        text = json_lib.dumps(data, ensure_ascii=False, indent=2)
        if len(text) > max_len:
            return text[:max_len] + "\n... (已截断)"
        return text
    except (TypeError, ValueError):
        return str(data)[:max_len]


class HostIPAdapter(HTTPAdapter):
    """自定义适配器：将域名请求直连到指定 IP，保留 Host 头和 SNI"""

    def __init__(self, host_ip: str, **kwargs):
        self.host_ip = host_ip
        super().__init__(**kwargs)

    def send(self, request, **kwargs):
        parsed = urlparse(request.url)
        hostname = parsed.hostname
        request.headers.setdefault("Host", hostname)
        request.url = request.url.replace(f"://{hostname}", f"://{self.host_ip}", 1)
        return super().send(request, **kwargs)


class APIResponse:
    """API 响应封装"""

    def __init__(self, response: requests.Response):
        self.raw = response
        self.status_code = response.status_code
        self.headers = response.headers
        self.elapsed = response.elapsed.total_seconds()
        self._json = None

    @property
    def json(self) -> dict:
        if self._json is None:
            try:
                self._json = self.raw.json()
            except ValueError:
                self._json = {}
        return self._json

    @property
    def code(self) -> int:
        """业务状态码"""
        return self.json.get("code", -1)

    @property
    def message(self) -> str:
        """业务消息"""
        return self.json.get("message", "")

    @property
    def data(self):
        """业务数据"""
        return self.json.get("data")

    @property
    def ok(self) -> bool:
        """HTTP 200 且业务码为 0"""
        return self.status_code == 200 and self.code == 0


class APIClient:
    """API 客户端基类 - 参数化构造，支持多业务模块复用"""

    def __init__(self, base_url: str = "", timeout: int = 30,
                 host_ip: str = "", token: Optional[str] = None,
                 logger=None):
        self.session = requests.Session()
        self.base_url = base_url
        self.timeout = timeout
        self._logger = logger

        # 测试环境 IP 直连
        if host_ip:
            adapter = HostIPAdapter(host_ip)
            self.session.mount("https://", adapter)
            self.session.mount("http://", adapter)
            self.session.verify = False

        self.session.headers.update({
            "Content-Type": "application/json",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        })

        if token:
            self.set_token(token)

    @classmethod
    def from_settings(cls, settings_class, token: Optional[str] = None, **kwargs):
        """从 Settings 类创建客户端实例"""
        return cls(
            base_url=settings_class.API_BASE_URL,
            timeout=settings_class.API_TIMEOUT,
            host_ip=getattr(settings_class, "API_HOST_IP", ""),
            token=token,
            **kwargs,
        )

    def set_token(self, token: str, header_name: str = "token"):
        """设置认证 token，默认写入 token 头，也可指定其他头名（如 Authorization）"""
        self.session.headers[header_name] = token

    def _url(self, path: str) -> str:
        return f"{self.base_url.rstrip('/')}/{path.lstrip('/')}"

    def _log(self, msg: str, level: str = "info"):
        if self._logger:
            getattr(self._logger, level)(msg)

    def _request(self, method: str, path: str, **kwargs) -> APIResponse:
        url = self._url(path)
        kwargs.setdefault("timeout", self.timeout)

        self._log(f"{method.upper()} {url}")
        if "json" in kwargs:
            self._log(f"请求体: {kwargs['json']}", "debug")

        resp = self.session.request(method, url, **kwargs)
        api_resp = APIResponse(resp)

        self._log(
            f"响应: {api_resp.status_code} | "
            f"业务码: {api_resp.code} | "
            f"耗时: {api_resp.elapsed:.3f}s"
        )

        # 记录请求/响应到 thread-local，供报告生成使用
        get_request_log().append({
            "method": method.upper(),
            "url": url,
            "request_params": kwargs.get("params"),
            "request_body": kwargs.get("json"),
            "status_code": api_resp.status_code,
            "biz_code": api_resp.code,
            "biz_message": api_resp.message,
            "elapsed": round(api_resp.elapsed, 3),
            "response_data": _truncate_json(api_resp.json),
        })

        return api_resp

    def get(self, path: str, params: dict = None, **kwargs) -> APIResponse:
        return self._request("GET", path, params=params, **kwargs)

    def post(self, path: str, json: dict = None, **kwargs) -> APIResponse:
        return self._request("POST", path, json=json, **kwargs)

    def put(self, path: str, json: dict = None, **kwargs) -> APIResponse:
        return self._request("PUT", path, json=json, **kwargs)

    def delete(self, path: str, **kwargs) -> APIResponse:
        return self._request("DELETE", path, **kwargs)

    def close(self):
        self.session.close()
