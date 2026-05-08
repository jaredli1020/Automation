"""飞书机器人通知 - 参数化版本，支持自定义标题前缀或完整标题"""

import requests
from autotest.logging import get_logger

logger = get_logger("feishu")

TEST_TYPE_NAMES = {
    "ui": "UI 自动化测试",
    "api": "接口自动化测试",
    "all": "全量测试（UI + 接口）",
}


def _format_duration(duration_str: str) -> str:
    """将 '1.23s' 或 '1.23' 格式化为可读时间"""
    try:
        seconds = float(str(duration_str).rstrip("s"))
    except (ValueError, AttributeError):
        return str(duration_str)
    if seconds < 60:
        return f"{seconds:.1f} 秒"
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{minutes} 分 {secs} 秒"


def _get_header_color(pass_rate_str: str) -> str:
    """根据通过率返回卡片 header 颜色模板"""
    try:
        rate = float(str(pass_rate_str).rstrip("%"))
    except (ValueError, AttributeError):
        return "red"
    if rate >= 100:
        return "green"
    elif rate >= 80:
        return "orange"
    return "red"


def build_card(summary: dict, report_path: str = "", title_prefix: str = "",
               report_title: str = "") -> dict:
    """构建飞书交互式卡片消息体"""
    test_type = TEST_TYPE_NAMES.get(summary.get("test_type", ""), "自动化测试")
    pass_rate = summary.get("pass_rate", "0%")
    color = _get_header_color(pass_rate)
    duration = _format_duration(summary.get("duration", "0s"))
    header_title = report_title if report_title else f"{title_prefix}{test_type}"

    elements = [
        {
            "tag": "div",
            "text": {
                "tag": "lark_md",
                "content": (
                    f"**测试类型：**{test_type}\n"
                    f"**执行时间：**{summary.get('start_time', '')} ~ {summary.get('end_time', '')}\n"
                    f"**总耗时：**{duration}"
                ),
            },
        },
        {"tag": "hr"},
        {
            "tag": "div",
            "text": {
                "tag": "lark_md",
                "content": (
                    f"✅ 通过：**{summary.get('passed', 0)}**　　"
                    f"❌ 失败：**{summary.get('failed', 0)}**\n"
                    f"⏭ 跳过：**{summary.get('skipped', 0)}**　　"
                    f"⚠ 错误：**{summary.get('error', 0)}**\n"
                    f"📊 通过率：**{pass_rate}**"
                ),
            },
        },
    ]

    # 失败用例列表（最多 10 条）
    failed_tests = summary.get("failed_tests", [])
    if failed_tests:
        items = failed_tests[:10]
        lines_list = []
        for t in items:
            if isinstance(t, dict):
                name = t["nodeid"].split("::")[-1]
                api_path = t.get("api_path", "")
                if api_path:
                    lines_list.append(f"• {name}　`{api_path}`")
                else:
                    lines_list.append(f"• {name}")
            else:
                lines_list.append(f"• {t.split('::')[-1]}")
        lines = "\n".join(lines_list)
        if len(failed_tests) > 10:
            lines += f"\n... 共 {len(failed_tests)} 条失败"
        elements.append({"tag": "hr"})
        elements.append({
            "tag": "div",
            "text": {"tag": "lark_md", "content": f"**失败用例：**\n{lines}"},
        })

    # 报告链接/路径
    if report_path:
        elements.append({"tag": "hr"})
        if report_path.startswith("http"):
            report_content = f"📄 **测试报告：**[点击查看]({report_path})"
        else:
            report_content = f"📄 **报告路径：**{report_path}"
        elements.append({
            "tag": "div",
            "text": {"tag": "lark_md", "content": report_content},
        })

    return {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {"tag": "plain_text", "content": f"🔬 {header_title}报告"},
                "template": color,
            },
            "elements": elements,
        },
    }


def send_card(webhook_url: str, card: dict) -> bool:
    """发送飞书卡片消息"""
    try:
        resp = requests.post(webhook_url, json=card, timeout=10)
        data = resp.json()
        if data.get("code") == 0:
            logger.info("飞书通知发送成功")
            return True
        logger.error(f"飞书通知发送失败: {data}")
        return False
    except Exception as e:
        logger.error(f"飞书通知发送异常: {e}")
        return False


def send_test_report(summary: dict, report_path: str = "",
                     webhook_url: str = "", notify_enabled: bool = True,
                     title_prefix: str = "", report_title: str = "") -> bool:
    """发送测试报告到飞书群"""
    if not notify_enabled:
        logger.info("飞书通知已禁用")
        return False

    if not webhook_url:
        logger.warning("未配置飞书 Webhook URL，跳过通知")
        return False

    card = build_card(summary, report_path, title_prefix=title_prefix, report_title=report_title)
    return send_card(webhook_url, card)
