"""Django 配置 - 通用 Web 服务"""

import os
from pathlib import Path

BASE_DIR = Path(os.environ.get("PROJECT_ROOT", Path.cwd()))

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "autotest-default-secret-change-me")

DEBUG = os.environ.get("DJANGO_DEBUG", "false").lower() == "true"

ALLOWED_HOSTS = ["*"]

INSTALLED_APPS = []

MIDDLEWARE = [
    "django.middleware.common.CommonMiddleware",
]

ROOT_URLCONF = os.environ.get("AUTOTEST_ROOT_URLCONF", "autotest.web.urls")

WSGI_APPLICATION = "autotest.web.wsgi.application"

DATABASES = {}

LANGUAGE_CODE = "zh-hans"
TIME_ZONE = "Asia/Shanghai"
USE_TZ = False
