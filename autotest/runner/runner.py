"""多业务测试运行器

业务项目通过注册 MODULE_CONFIG 暴露测试模块信息，runner 动态发现并调度。
每个业务模块的 module.py 需定义：

    MODULE_CONFIG = {
        "name": "demo",
        "display_name": "示例业务",
        "settings_class": "demo.config.settings.Settings",   # 可选，用于加载环境
        "web_urls": "demo.web.urls",                         # 可选
        "test_modules": {                                    # 可选，用于 --list
            "api": {"login": "登录认证测试", ...},
            "ui": {"home": "首页测试", ...},
        },
        "report_module_names": {"api/login": "登录认证"},     # 可选，报告中文名映射
    }
"""

import os
import sys
import json
import subprocess
import importlib
from pathlib import Path


def _get_project_root() -> Path:
    return Path(os.environ.get("PROJECT_ROOT", Path.cwd()))


def _get_reports_dir() -> Path:
    return _get_project_root() / "reports"


def _get_summary_path() -> Path:
    return _get_reports_dir() / "test_summary.json"


# 已注册的业务模块
_BUSINESS_MODULES: dict = {}
# 业务模块发现列表 - 业务项目通过 register_modules() 注册
_MODULE_NAMES: list = []


def register_modules(names: list):
    """由业务项目注册可发现的业务模块名列表"""
    global _MODULE_NAMES
    _MODULE_NAMES = list(names)
    _BUSINESS_MODULES.clear()


def _discover_modules():
    """动态发现并加载所有业务模块的 MODULE_CONFIG"""
    if _BUSINESS_MODULES:
        return

    # 从环境变量读取模块列表作为补充
    if not _MODULE_NAMES:
        env_names = os.environ.get("AUTOTEST_MODULES", "")
        if env_names:
            _MODULE_NAMES.extend([n.strip() for n in env_names.split(",") if n.strip()])

    project_root = _get_project_root()
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    for name in _MODULE_NAMES:
        try:
            mod = importlib.import_module(f"{name}.module")
            config = getattr(mod, "MODULE_CONFIG", None)
            if config:
                _BUSINESS_MODULES[name] = config
        except ImportError:
            pass


def get_module_config(business: str) -> dict:
    _discover_modules()
    return _BUSINESS_MODULES.get(business, {})


def list_modules() -> dict:
    """列出所有可用业务模块"""
    _discover_modules()
    result = {}
    for name, config in _BUSINESS_MODULES.items():
        result[name] = {
            "display_name": config.get("display_name", name),
            "test_modules": config.get("test_modules", {}),
        }
    return result


def _resolve_test_path(business: str, test_type: str, module: str = None) -> str:
    """解析测试路径 tests/{business}/{type}/{module}/"""
    project_root = _get_project_root()
    if module:
        path = f"tests/{business}/{test_type}/{module}/"
    else:
        path = f"tests/{business}/{test_type}/"
    if (project_root / path).exists():
        return path
    return path  # 返回路径让 pytest 报错


def run_pytest(path: str = None, marker: str = None, test_type: str = "ui",
               extra_args: list = None) -> dict:
    """执行 pytest 并返回结果"""
    project_root = _get_project_root()
    reports_dir = _get_reports_dir()
    reports_dir.mkdir(parents=True, exist_ok=True)

    python_exe = sys.executable
    cmd = [python_exe, "-m", "pytest", "-v", "--tb=short"]

    if path:
        cmd.append(path)
    if marker:
        cmd.extend(["-m", marker])
    if extra_args:
        cmd.extend(extra_args)

    print(f"\n执行命令: {' '.join(cmd)}")
    print("=" * 60)

    env = os.environ.copy()
    env["_RUN_TEST_NOTIFY_HANDLED"] = "1"
    env["PROJECT_ROOT"] = str(project_root)
    result = subprocess.run(cmd, cwd=str(project_root), env=env)

    report_path = ""
    summary_path = _get_summary_path()
    if summary_path.exists():
        try:
            with open(summary_path, "r", encoding="utf-8") as f:
                summary = json.load(f)
            report_path = summary.get("report_path", "")
        except Exception:
            pass

    return {
        "returncode": result.returncode,
        "report_path": report_path,
        "command": " ".join(cmd),
    }


def _parse_target(target: str) -> tuple:
    """解析目标字符串 → (business, test_type, module)

    支持格式：
      demo:api           -> ("demo", "api", None)
      demo:ui:home       -> ("demo", "ui", "home")
      demo               -> ("demo", "all", None)
      all                -> (None, "all", None)
    """
    _discover_modules()

    if target == "all":
        return (None, "all", None)

    parts = target.split(":")
    if len(parts) == 1:
        if parts[0] in _BUSINESS_MODULES:
            return (parts[0], "all", None)
        return (None, parts[0], None)

    if len(parts) == 2:
        first, second = parts
        if first in _BUSINESS_MODULES:
            return (first, second, None)
        return (None, first, second)

    if len(parts) == 3:
        business, second, third = parts
        if business in _BUSINESS_MODULES:
            return (business, second, third)
        return (None, second, third)

    return (None, target, None)


def run(target: str = "all", modules: list = None, extra_args: list = None) -> dict:
    """统一运行入口，供命令行和外部接口调用"""
    business, test_type, module = _parse_target(target)

    if modules:
        paths = []
        for m in modules:
            paths.append(_resolve_test_path(business or "", test_type, m))
        return run_pytest(path=" ".join(paths), test_type=test_type, extra_args=extra_args)

    if module:
        path = _resolve_test_path(business or "", test_type, module)
        return run_pytest(path=path, test_type=test_type, extra_args=extra_args)

    if business and test_type != "all":
        path = _resolve_test_path(business, test_type)
        return run_pytest(path=path, test_type=test_type, extra_args=extra_args)

    if business and test_type == "all":
        path = f"tests/{business}/"
        if not (_get_project_root() / path).exists():
            path = "tests/"
        return run_pytest(path=path, test_type="all", extra_args=extra_args)

    return run_pytest(test_type="all", extra_args=extra_args)


def load_settings_for_business(business: str, env_name: str):
    """加载业务模块的 Settings 类并切换环境"""
    if not business:
        return None
    try:
        config = get_module_config(business)
        settings_path = config.get("settings_class") or f"{business}.config.settings.Settings"
        module_path, cls_name = settings_path.rsplit(".", 1)
        settings_mod = importlib.import_module(module_path)
        settings_cls = getattr(settings_mod, cls_name)
        settings_cls.load_env(env_name)
        return settings_cls
    except (ImportError, AttributeError, ValueError) as e:
        print(f"[runner] 加载 {business} Settings 失败: {e}")
        return None


def send_feishu_notify(report_path: str = "", business: str = ""):
    """读取测试摘要并发送飞书通知"""
    reports_dir = _get_reports_dir()
    biz_summary = reports_dir / f"test_summary_{business}.json"
    summary_path = biz_summary if biz_summary.exists() else _get_summary_path()

    if not summary_path.exists():
        print("[通知] 未找到测试摘要文件，跳过飞书通知")
        return

    try:
        with open(summary_path, "r", encoding="utf-8") as f:
            summary = json.load(f)

        if not report_path:
            report_path = summary.get("report_path", "")

        # 将本地路径转为 HTTP URL（若业务 Settings 配置了 REPORT_BASE_URL）
        webhook_url = ""
        notify_enabled = True
        settings_cls = load_settings_for_business(business, os.environ.get("ENV", "prod"))
        if settings_cls:
            webhook_url = getattr(settings_cls, "FEISHU_WEBHOOK_URL", "")
            notify_enabled = getattr(settings_cls, "FEISHU_NOTIFY_ENABLED", True)
            base_url = getattr(settings_cls, "REPORT_BASE_URL", "").rstrip("/")
            if report_path and not report_path.startswith("http") and base_url and base_url != "http://localhost:8000":
                filename = Path(report_path).name
                report_path = f"{base_url}/reports/{filename}"

        if not webhook_url:
            print(f"[通知] {business or '默认'} 未配置 FEISHU_WEBHOOK_URL，跳过飞书通知")
            return

        from autotest.utils.feishu import send_test_report
        report_title = summary.get("report_title", "")
        send_test_report(
            summary, report_path,
            webhook_url=webhook_url,
            notify_enabled=notify_enabled,
            report_title=report_title,
        )
    except Exception as e:
        print(f"[通知] 飞书通知发送失败: {e}")


# 向后兼容别名
_send_feishu_notify = send_feishu_notify
