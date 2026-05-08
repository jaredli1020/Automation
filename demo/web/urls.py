"""demo 业务专用 Web 路由（可选）

通过在 autotest.web.settings 或 Django settings override 中添加：

    AUTOTEST_BUSINESS_URLS = [("demo/", "demo.web.urls")]

就可以把这些路由挂载到 /demo/ 前缀下。
"""

from django.urls import path
from django.http import JsonResponse


def ping(request):
    return JsonResponse({"code": 0, "message": "pong", "data": {"business": "demo"}})


urlpatterns = [
    path("api/ping/", ping),
]
