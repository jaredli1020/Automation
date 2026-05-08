"""自定义 HTML 测试报告生成器 - 通用版本

生成 self-contained HTML 报告，支持多业务模块。
模块中文名映射和标题前缀通过参数传入，不硬编码任何业务字段。

报告渲染使用内置的 report_style.css 和 report_script.js，业务方可以
覆盖这两个文件来定制报告样式。
"""

import json
import html as html_lib
from datetime import datetime
from pathlib import Path

MAX_TREND_RECORDS = 30

TEST_TYPE_NAMES = {
    "ui": "UI 自动化测试",
    "api": "接口自动化测试",
    "all": "全量测试",
}

# 框架自带的报告静态资源目录
_ASSETS_DIR = Path(__file__).parent / "report_assets"


def generate_html_report(test_type: str, results: list,
                         start_time: datetime, end_time: datetime,
                         module_names: dict = None,
                         title_prefix: str = "",
                         report_title: str = "",
                         reports_dir: Path = None) -> str:
    """生成 HTML 报告，返回文件路径。

    Args:
        test_type: 测试类型 (ui / api / all)
        results: 测试结果列表，每条需包含 nodeid/name/outcome/duration/module 字段
        start_time: 开始时间
        end_time: 结束时间
        module_names: 模块代号到显示名映射，如 {"api/login": "登录认证"}
        title_prefix: 标题前缀，如 "魔剪"（用于文件名和默认标题）
        report_title: 完整报告标题（优先级高于 title_prefix）
        reports_dir: 报告输出目录，必填
    """
    if reports_dir is None:
        raise ValueError("reports_dir 不能为空")

    reports_dir = Path(reports_dir)
    reports_dir.mkdir(parents=True, exist_ok=True)
    module_names = module_names or {}

    total = len(results)
    passed = sum(1 for r in results if r["outcome"] == "passed")
    failed = sum(1 for r in results if r["outcome"] == "failed")
    skipped = sum(1 for r in results if r["outcome"] == "skipped")
    error = total - passed - failed - skipped
    duration = (end_time - start_time).total_seconds()
    pass_rate = (passed / total * 100) if total > 0 else 0

    summary = {
        "test_type": test_type,
        "total": total,
        "passed": passed,
        "failed": failed,
        "skipped": skipped,
        "error": error,
        "pass_rate": pass_rate,
        "duration": duration,
        "start_time": start_time.strftime("%Y-%m-%d %H:%M:%S"),
        "end_time": end_time.strftime("%Y-%m-%d %H:%M:%S"),
    }

    # 趋势文件按 title_prefix 隔离，避免不同业务数据混在一起
    trend_tag = title_prefix.replace(" ", "_") if title_prefix else "default"
    trend_file = reports_dir / f"test_trend_{trend_tag}.json"
    trend_data = _update_trend(summary, trend_file)

    # 为每条结果添加索引，分离截图数据
    screenshots = {}
    for i, r in enumerate(results):
        r["_idx"] = i
        if r.get("screenshot_b64"):
            screenshots[i] = r["screenshot_b64"]
            r["has_screenshot"] = True
            r.pop("screenshot_b64", None)
        else:
            r["has_screenshot"] = False
            r.pop("screenshot_b64", None)

    report_html = _render_html(test_type, summary, results, trend_data,
                               screenshots, module_names, title_prefix,
                               report_title)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    prefix_tag = f"{title_prefix}_" if title_prefix else ""
    filename = f"{prefix_tag}{test_type}_report_{timestamp}.html"
    filepath = reports_dir / filename
    filepath.write_text(report_html, encoding="utf-8")
    return str(filepath)


def _update_trend(summary: dict, trend_file: Path) -> list:
    """追加当前结果到趋势文件，返回趋势列表"""
    trend = []
    try:
        if trend_file.exists():
            trend = json.loads(trend_file.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        trend = []

    trend.append({
        "date": summary["start_time"],
        "test_type": summary["test_type"],
        "total": summary["total"],
        "passed": summary["passed"],
        "failed": summary["failed"],
        "skipped": summary["skipped"],
        "pass_rate": round(summary["pass_rate"], 1),
        "duration": round(summary["duration"], 1),
    })

    if len(trend) > MAX_TREND_RECORDS:
        trend = trend[-MAX_TREND_RECORDS:]

    try:
        trend_file.write_text(json.dumps(trend, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        pass

    return trend


def _format_duration(seconds: float) -> str:
    if seconds < 60:
        return f"{seconds:.1f} 秒"
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{minutes} 分 {secs} 秒"


def _safe_json_embed(data) -> str:
    """将数据序列化为可安全嵌入 <script type=application/json> 的字符串"""
    text = json.dumps(data, ensure_ascii=False)
    text = text.replace("</", "<\\/")
    return text


def _read_asset(filename: str) -> str:
    """读取报告资源文件"""
    path = _ASSETS_DIR / filename
    if path.exists():
        return path.read_text(encoding="utf-8")
    return ""


def _render_html(test_type: str, summary: dict, results: list,
                 trend_data: list, screenshots: dict,
                 module_names: dict, title_prefix: str,
                 report_title: str = "") -> str:
    type_name = TEST_TYPE_NAMES.get(test_type, "自动化测试")
    full_title = report_title if report_title else (f"{title_prefix}{type_name}" if title_prefix else type_name)
    total = summary["total"]
    passed = summary["passed"]
    failed = summary["failed"]
    skipped = summary["skipped"]
    error = summary["error"]
    pass_rate = summary["pass_rate"]
    duration_str = _format_duration(summary["duration"])

    if total > 0:
        p_deg = round(passed / total * 360)
        f_deg = p_deg + round(failed / total * 360)
        s_deg = f_deg + round(skipped / total * 360)
    else:
        p_deg = f_deg = s_deg = 0

    filtered_trend = [t for t in trend_data if t["test_type"] == test_type][-20:]
    trend_json = _safe_json_embed(filtered_trend)
    results_json = _safe_json_embed(results)
    screenshots_json = _safe_json_embed(screenshots)
    module_names_json = _safe_json_embed(module_names)

    # 收集模块统计，生成左侧导航
    mod_order = []
    mod_stats = {}
    for r in results:
        m = r.get("module", "other")
        if m not in mod_stats:
            mod_stats[m] = {"total": 0, "passed": 0, "failed": 0}
            mod_order.append(m)
        mod_stats[m]["total"] += 1
        if r["outcome"] == "passed":
            mod_stats[m]["passed"] += 1
        elif r["outcome"] in ("failed", "error"):
            mod_stats[m]["failed"] += 1

    nav_mods = ""
    for m in mod_order:
        s = mod_stats[m]
        label = html_lib.escape(module_names.get(m, m))
        cls = "nb-fail" if s["failed"] > 0 else "nb-pass"
        val = s["failed"] if s["failed"] > 0 else s["total"]
        nav_mods += (
            f'<a class="nav-item" onclick="navTo(this)" data-mod="{m}">'
            f'{label}<span class="nav-badge {cls}">{val}</span></a>\n'
        )

    if len(filtered_trend) >= 2:
        trend_inner = (
            '<canvas id="trendChart"></canvas>'
            '<div class="legend">'
            '<span><i style="background:#10b981"></i>通过</span>'
            '<span><i style="background:#ef4444"></i>失败</span>'
            '<span style="color:#667eea">— 通过率</span>'
            '</div>'
        )
    else:
        trend_inner = '<div class="trend-empty">暂无足够历史数据（至少需要 2 次执行记录）</div>'

    css_text = _read_asset("report_style.css")
    js_text = _read_asset("report_script.js")

    donut_css = (
        f".donut{{width:130px;height:130px;border-radius:50%;"
        f"background:conic-gradient(#10b981 0deg {p_deg}deg,"
        f"#ef4444 {p_deg}deg {f_deg}deg,"
        f"#f59e0b {f_deg}deg {s_deg}deg,"
        f"#e5e7eb {s_deg}deg 360deg);"
        f"position:relative;margin-bottom:10px}}"
        f".donut::after{{content:'{pass_rate:.1f}%';position:absolute;inset:22px;"
        f"background:#fff;border-radius:50%;display:flex;align-items:center;"
        f"justify-content:center;font-size:22px;font-weight:700;color:#333}}"
    )

    logo_b64 = _read_asset("report_logo.txt").strip()
    logo_html = (
        f'<img src="data:image/png;base64,{logo_b64}" '
        f'style="height:28px;margin-right:12px;vertical-align:middle;border-radius:4px">'
    ) if logo_b64 else ""

    parts = [
        '<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8">',
        '<meta name="viewport" content="width=device-width,initial-scale=1.0">',
        f'<title>{full_title}报告</title>',
        f'<style>{css_text}\n{donut_css}</style>',
        '</head><body>',
        '<div class="topbar">',
        f'<div style="display:flex;align-items:center">{logo_html}<h1>{full_title}报告</h1></div>',
        f'<span class="topbar-info">{summary["start_time"]} ~ {summary["end_time"]}'
        f'　|　{duration_str}　|　{total} 个用例</span>',
        '</div>',
        '<div class="app">',
        '<nav class="sidebar">',
        '<div class="nav-label">导航</div>',
        f'<a class="nav-item active" onclick="navTo(this)" data-mod="">概览'
        f'<span class="nav-badge nb-default">{total}</span></a>',
        f'<a class="nav-item" onclick="navTo(this)" data-mod="__all__">用例详情'
        f'<span class="nav-badge nb-default">{total}</span></a>',
        '<div class="nav-divider"></div>',
        '<div class="nav-label">测试模块</div>',
        nav_mods,
        '</nav>',
        '<div class="main" id="mainArea">',
        '<div id="page-overview" class="page active">',
        '<div class="ov-grid">',
        '<div class="donut-card"><div class="donut"></div><div class="donut-lbl">通过率</div></div>',
        '<div class="stat-cards">',
        f'<div class="stat-card sc-pass"><div class="num">{passed}</div><div class="lbl">通过</div></div>',
        f'<div class="stat-card sc-fail"><div class="num">{failed}</div><div class="lbl">失败</div></div>',
        f'<div class="stat-card sc-skip"><div class="num">{skipped}</div><div class="lbl">跳过</div></div>',
        f'<div class="stat-card sc-err"><div class="num">{error}</div><div class="lbl">错误</div></div>',
        f'<div class="stat-card sc-time"><div class="num">{duration_str}</div><div class="lbl">总耗时</div></div>',
        '</div></div>',
        f'<div class="trend-card"><h3>执行趋势</h3><div id="trendWrap">{trend_inner}</div></div>',
        '<div id="modOverview" class="mod-overview"></div>',
        '</div>',
        '<div id="page-list" class="page">',
        '<div class="page-title" id="pageTitle">用例详情</div>',
        '<div class="list-card">',
        '<div class="filter-bar" id="filterBar">',
        f'<button class="filter-btn active" onclick="applyFilter(\'all\',this)">全部 ({total})</button>',
        f'<button class="filter-btn" onclick="applyFilter(\'passed\',this)">通过 ({passed})</button>',
        f'<button class="filter-btn" onclick="applyFilter(\'failed\',this)">失败 ({failed})</button>',
        f'<button class="filter-btn" onclick="applyFilter(\'skipped\',this)">跳过 ({skipped})</button>',
        '<input class="search-input" type="text" placeholder="搜索用例名称/接口..." oninput="applySearch(this.value)">',
        '</div>',
        '<div id="testContainer"></div>',
        '<div id="pagination" class="pagination"></div>',
        '</div></div>',
        '</div></div>',
        '<div class="overlay" id="overlay" onclick="closeScreenshot()"></div>',
        f'<script type="application/json" id="d-r">{results_json}</script>',
        f'<script type="application/json" id="d-s">{screenshots_json}</script>',
        f'<script type="application/json" id="d-m">{module_names_json}</script>',
        f'<script type="application/json" id="d-t">{trend_json}</script>',
        f'<script>{js_text}</script>',
        '</body></html>',
    ]
    return "\n".join(parts)
