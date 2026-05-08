"""通用 Pytest hooks 和报告收集逻辑

业务项目在自己的 conftest.py 中导入本模块的 hooks，或继承关键 fixture：

    # <project>/tests/conftest.py
    from autotest.runner.conftest_hooks import *  # noqa
"""

import os
import re
import time
import json
import pytest
import importlib
from datetime import datetime
from pathlib import Path

from autotest.config.base_settings import BaseSettings
from autotest.api.client import get_request_log, clear_request_log


# ==================== 内部状态 ====================

_test_type = "ui"
_test_results = []
_session_start_time = None
_active_business = ""


# ==================== 工具函数 ====================

def sanitize_filename(name: str) -> str:
    invalid_chars = r'[<>:"/\\|?*]'
    name = re.sub(invalid_chars, "_", name)
    if len(name) > 100:
        name = name[:100]
    return name


def extract_error_reason(report) -> str:
    """从 pytest report 中提取错误原因"""
    if not report.longrepr:
        return "未知错误"

    error_str = str(report.longrepr)

    error_patterns = [
        (r"Timeout \d+ms exceeded.*waiting for locator", "元素等待超时"),
        (r"locator\.click", "点击元素失败"),
        (r"locator\.fill", "填充文本失败"),
        (r"Element is not visible", "元素不可见"),
        (r"Element is not attached", "元素已分离"),
        (r"Element is outside of the viewport", "元素在视口外"),
        (r"AssertionError", "断言失败"),
        (r"Connection refused", "连接被拒绝"),
        (r"Target closed", "目标已关闭"),
        (r"Browser has been closed", "浏览器已关闭"),
        (r"Page closed", "页面已关闭"),
        (r"TimeoutError", "超时错误"),
        (r"Timeout", "操作超时"),
    ]

    for pattern, chinese_reason in error_patterns:
        if re.search(pattern, error_str, re.IGNORECASE):
            return chinese_reason

    for line in error_str.split("\n"):
        if "Error" in line or "assert" in line.lower():
            clean_line = line.strip()[:50]
            return sanitize_filename(clean_line) if clean_line else "测试失败"

    return "测试失败"


def _detect_business(nodeid: str) -> str:
    """从 nodeid 检测业务模块（tests/{business}/... 结构）"""
    path = nodeid.replace("\\", "/")
    m = re.search(r"tests/([^/]+)/", path)
    if m:
        return m.group(1)
    return "unknown"


def _extract_module(nodeid: str) -> str:
    """从 nodeid 提取模块路径 {type}/{module}"""
    parts = nodeid.replace("\\", "/").split("::")
    file_path = parts[0]
    if "tests/" in file_path:
        after_tests = file_path.split("tests/", 1)[1]
        segments = after_tests.split("/")
        # tests/{business}/{type}/{module}/test_xxx.py -> {type}/{module}
        if len(segments) >= 3:
            return "/".join(segments[1:-1])
        if len(segments) == 2:
            return segments[0]
    return "other"


def _extract_api_path(item) -> str:
    """从 API 测试模块提取接口路径（约定 _yaml_data.path 字段）"""
    try:
        module = item.module
        yaml_data = getattr(module, "_yaml_data", None)
        if yaml_data and isinstance(yaml_data, dict):
            return yaml_data.get("path", "")
    except Exception:
        pass
    return ""


def _get_module_config(business: str) -> dict:
    if not business:
        return {}
    try:
        mod = importlib.import_module(f"{business}.module")
        return getattr(mod, "MODULE_CONFIG", {})
    except ImportError:
        return {}


def _get_display_name(business: str) -> str:
    config = _get_module_config(business)
    return config.get("display_name", business)


def _get_report_title(business: str, test_type: str) -> str:
    type_name = {"api": "接口测试", "ui": "UI测试", "all": "全量测试"}.get(test_type, "自动化测试")
    biz_cn = _get_display_name(business)
    return f"{biz_cn}{type_name}"


def _get_settings_for_business(business: str):
    if not business:
        return BaseSettings
    try:
        config = _get_module_config(business)
        settings_path = config.get("settings_class") or f"{business}.config.settings.Settings"
        module_path, cls_name = settings_path.rsplit(".", 1)
        settings_mod = importlib.import_module(module_path)
        return getattr(settings_mod, cls_name)
    except (ImportError, AttributeError, ValueError):
        return BaseSettings


def _cleanup_old_reports(max_age_days: int = 3):
    reports_dir = BaseSettings.REPORTS_DIR
    if not reports_dir.exists():
        return
    cutoff = time.time() - max_age_days * 86400
    removed = 0
    for f in reports_dir.iterdir():
        if f.is_file() and f.suffix in (".html", ".log"):
            try:
                if os.path.getmtime(f) < cutoff:
                    f.unlink()
                    removed += 1
            except OSError:
                pass
    if removed:
        print(f"[清理] 已删除 {removed} 个过期报告文件（>{max_age_days} 天）")


def _get_test_chinese_name(item) -> str:
    """从 docstring 第一行获取中文测试名"""
    if item.function.__doc__:
        doc = item.function.__doc__.strip()
        if doc:
            first_line = doc.split("\n")[0].strip()
            if first_line:
                return sanitize_filename(first_line)
    return item.name


# ==================== Pytest Hooks ====================

def pytest_configure(config):
    """配置 pytest，根据运行参数判断测试类型，加载环境配置"""
    global _test_type, _active_business
    args = [str(a).replace("\\", "/") for a in config.invocation_params.args]
    has_api = any("api" in a for a in args)
    has_ui = any("ui" in a for a in args)

    if has_ui and not has_api:
        _test_type = "ui"
    elif has_api and not has_ui:
        _test_type = "api"
    else:
        _test_type = "all"

    # 检测业务模块 - 从第一个匹配 tests/{business}/ 的路径中提取
    for a in args:
        m = re.search(r"tests/([^/]+)/", a)
        if m:
            _active_business = m.group(1)
            break

    # 加载环境配置
    env_name = os.environ.get("ENV", "prod")
    settings_cls = _get_settings_for_business(_active_business)
    try:
        settings_cls.load_env(env_name)
    except (ValueError, AttributeError):
        pass

    biz_name = _get_display_name(_active_business)
    type_names = {"api": "接口自动化测试", "ui": "UI 自动化测试", "all": "全量测试"}
    config._metadata = {
        "项目名称": f"{biz_name}{type_names.get(_test_type, '自动化测试')}",
        "测试框架": "Pytest + Playwright + Requests",
        "测试环境": env_name,
        "执行时间": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


def pytest_sessionstart(session):
    """测试开始前清理旧报告、重置截图目录"""
    global _session_start_time
    _session_start_time = datetime.now()
    _cleanup_old_reports(max_age_days=3)

    if _test_type == "api":
        return

    import shutil
    screenshots_dir = BaseSettings.SCREENSHOTS_DIR / (_active_business or "default")
    if screenshots_dir.exists():
        shutil.rmtree(screenshots_dir)
    screenshots_dir.mkdir(parents=True, exist_ok=True)


def pytest_runtest_setup(item):
    """每个测试开始前清空 API 请求记录"""
    clear_request_log()


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """测试失败时自动截图并收集结果"""
    outcome = yield
    report = outcome.get_result()

    if report.when == "call":
        module = _extract_module(item.nodeid)
        api_path = _extract_api_path(item)
        api_requests = list(get_request_log())

        result_entry = {
            "nodeid": item.nodeid,
            "name": _get_test_chinese_name(item),
            "outcome": report.outcome,
            "duration": report.duration,
            "error_msg": "",
            "screenshot_b64": "",
            "module": module,
            "api_path": api_path,
            "api_requests": api_requests,
        }
        if report.outcome == "failed":
            result_entry["error_msg"] = extract_error_reason(report)
        _test_results.append(result_entry)
    elif report.when == "setup" and report.failed:
        module = _extract_module(item.nodeid)
        api_path = _extract_api_path(item)
        result_entry = {
            "nodeid": item.nodeid,
            "name": _get_test_chinese_name(item),
            "outcome": "error",
            "duration": report.duration,
            "error_msg": extract_error_reason(report),
            "screenshot_b64": "",
            "module": module,
            "api_path": api_path,
            "api_requests": [],
        }
        _test_results.append(result_entry)

    # UI 失败自动截图 - 查找 funcargs 中包含 .page 属性的 fixture
    if report.when == "call" and report.failed:
        for fixture_name, fixture_val in item.funcargs.items():
            if hasattr(fixture_val, "page"):
                try:
                    import base64
                    test_name = _get_test_chinese_name(item)
                    error_reason = extract_error_reason(report)
                    timestamp = datetime.now().strftime("%H%M%S")
                    screenshot_name = sanitize_filename(f"{test_name}_{error_reason}_{timestamp}")

                    BaseSettings.ensure_dirs()
                    biz = _detect_business(item.nodeid)
                    ss_dir = BaseSettings.SCREENSHOTS_DIR / biz
                    ss_dir.mkdir(parents=True, exist_ok=True)
                    screenshot_path = ss_dir / f"{screenshot_name}.png"

                    screenshot_bytes = fixture_val.page.screenshot()
                    screenshot_path.write_bytes(screenshot_bytes)
                    if _test_results:
                        _test_results[-1]["screenshot_b64"] = base64.b64encode(screenshot_bytes).decode("utf-8")
                    print(f"\n截图已保存: {screenshot_path}")
                    break
                except Exception as e:
                    print(f"\n截图失败: {e}")


@pytest.fixture(autouse=True)
def setup_dirs():
    BaseSettings.ensure_dirs()


# ==================== 会话结束 ====================

def _send_notify_from_conftest(summary: dict):
    """pytest 直接执行时发送飞书通知（runner 调用时会由 runner 负责）"""
    try:
        business = summary.get("business", "")
        settings_cls = _get_settings_for_business(business)
        webhook_url = getattr(settings_cls, "FEISHU_WEBHOOK_URL", "")
        if not webhook_url:
            print(f"\n[通知] 未配置 FEISHU_WEBHOOK_URL，跳过飞书通知")
            return

        from autotest.utils.feishu import send_test_report
        send_test_report(
            summary,
            summary.get("report_path", ""),
            webhook_url=webhook_url,
            notify_enabled=getattr(settings_cls, "FEISHU_NOTIFY_ENABLED", True),
            report_title=summary.get("report_title", ""),
        )
    except Exception as e:
        print(f"\n[通知] 飞书通知发送失败: {e}")


def pytest_sessionfinish(session, exitstatus):
    """生成 HTML 报告 + 摘要 + 飞书通知"""
    end_time = datetime.now()
    passed = sum(1 for r in _test_results if r["outcome"] == "passed")
    failed = sum(1 for r in _test_results if r["outcome"] == "failed")
    skipped = sum(1 for r in _test_results if r["outcome"] == "skipped")
    error = sum(1 for r in _test_results if r["outcome"] == "error")
    total = len(_test_results)
    duration = (end_time - _session_start_time).total_seconds() if _session_start_time else 0

    failed_tests = []
    for r in _test_results:
        if r["outcome"] in ("failed", "error"):
            entry = {"nodeid": r["nodeid"]}
            if r.get("api_path"):
                entry["api_path"] = r["api_path"]
            failed_tests.append(entry)

    summary = {
        "test_type": _test_type,
        "business": _active_business,
        "total": total,
        "passed": passed,
        "failed": failed,
        "skipped": skipped,
        "error": error,
        "pass_rate": f"{(passed / total * 100):.1f}%" if total > 0 else "0%",
        "duration": f"{duration:.2f}s",
        "start_time": _session_start_time.strftime("%Y-%m-%d %H:%M:%S") if _session_start_time else "",
        "end_time": end_time.strftime("%Y-%m-%d %H:%M:%S"),
        "failed_tests": failed_tests,
        "report_title": _get_report_title(_active_business, _test_type),
    }

    # 生成 HTML 报告
    try:
        biz_display = _get_display_name(_active_business)
        mod_config = _get_module_config(_active_business)
        module_names = mod_config.get("report_module_names", {})

        from autotest.utils.report_generator import generate_html_report
        report_path = generate_html_report(
            test_type=_test_type,
            results=_test_results,
            start_time=_session_start_time,
            end_time=end_time,
            module_names=module_names,
            title_prefix=biz_display,
            report_title=summary["report_title"],
            reports_dir=BaseSettings.REPORTS_DIR,
        )
        summary["report_path"] = report_path
        print(f"[报告] HTML 报告已生成: {report_path}")
    except Exception as e:
        print(f"[报告] HTML 报告生成失败: {e}")

    # 按业务隔离的摘要 + 通用摘要
    try:
        BaseSettings.ensure_dirs()
        biz_key = _active_business or "default"
        biz_summary_path = BaseSettings.REPORTS_DIR / f"test_summary_{biz_key}.json"
        general_path = BaseSettings.REPORTS_DIR / "test_summary.json"
        for p in (biz_summary_path, general_path):
            with open(p, "w", encoding="utf-8") as f:
                json.dump(summary, f, ensure_ascii=False, indent=2)
        print(f"\n[摘要] 测试摘要已写入: {biz_summary_path}")
    except Exception as e:
        print(f"\n[摘要] 写入测试摘要失败: {e}")

    # 飞书通知（runner 调用时设置了 _RUN_TEST_NOTIFY_HANDLED，避免重复）
    if not os.environ.get("_RUN_TEST_NOTIFY_HANDLED"):
        _send_notify_from_conftest(summary)
