"""URL 路由 - 通用版本

核心路由：
  /api/run         触发测试
  /api/jobs        任务列表
  /api/jobs/<id>   单个任务
  /api/modules     业务模块
  /api/schedule    定时任务
  /api/health      健康检查
  /reports/<path>  报告文件

业务项目可在 django settings 中定义 AUTOTEST_BUSINESS_URLS：

    AUTOTEST_BUSINESS_URLS = [
        ("demo/", "demo.web.urls"),
    ]
"""

from django.urls import path, re_path, include
from django.http import FileResponse, Http404
from django.conf import settings as django_settings

from autotest.config.base_settings import BaseSettings
from . import views


def serve_report(request, path):
    """托管报告文件"""
    file_path = BaseSettings.REPORTS_DIR / path
    if not file_path.exists() or not file_path.is_file():
        raise Http404
    try:
        file_path.resolve().relative_to(BaseSettings.REPORTS_DIR.resolve())
    except ValueError:
        raise Http404
    return FileResponse(open(file_path, "rb"), content_type="text/html")


urlpatterns = [
    path("api/run", views.run_test),
    path("api/jobs", views.get_jobs),
    path("api/jobs/<str:job_id>", views.get_job),
    path("api/modules", views.get_modules),
    path("api/schedule", views.get_schedule),
    path("api/health", views.health),
    re_path(r"^reports/(?P<path>.+)$", serve_report),
]

# 动态 include 业务模块路由（由业务项目通过 django settings 配置）
_business_urls = getattr(django_settings, "AUTOTEST_BUSINESS_URLS", [])
for prefix, module_path in _business_urls:
    try:
        urlpatterns.append(path(prefix, include(module_path)))
    except Exception:
        pass
