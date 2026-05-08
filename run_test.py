#!/usr/bin/env python
"""测试运行器入口 - 业务项目的 CLI

用法:
  python run_test.py demo:api                  # 运行 demo 业务接口测试
  python run_test.py demo:ui:home              # 运行 demo 首页 UI 测试
  python run_test.py --list                    # 列出所有业务模块
  python run_test.py --env test demo:api       # 指定测试环境
  python run_test.py --no-notify demo:api      # 跳过飞书通知
  python run_test.py demo:api -- -k test_login # 传递额外 pytest 参数

业务项目在本文件顶部注册自己的业务模块名：
  from autotest.runner import register_modules
  register_modules(["demo", "another_business"])
"""

import os
import sys
import json
import argparse
from pathlib import Path

# 将项目根目录加入 sys.path
PROJECT_ROOT = Path(__file__).parent.resolve()
sys.path.insert(0, str(PROJECT_ROOT))
os.environ.setdefault("PROJECT_ROOT", str(PROJECT_ROOT))

from autotest.runner import register_modules, list_modules, run, send_feishu_notify, load_settings_for_business
from autotest.runner.runner import _parse_target


# ==================== 业务模块注册 ====================
# 在此添加业务目录名。框架会自动查找 {business}/module.py 中的 MODULE_CONFIG
BUSINESS_MODULES = [
    "demo",
]
register_modules(BUSINESS_MODULES)


def _send_feishu_notify(report_path: str = "", business: str = ""):
    """供 scheduler 和 web 视图回调的通知函数"""
    send_feishu_notify(report_path, business)


def main():
    parser = argparse.ArgumentParser(
        description="自动化测试运行器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("targets", nargs="*", default=["all"],
                        help="目标: business:type:module 格式")
    parser.add_argument("--list", action="store_true", help="列出所有业务模块")
    parser.add_argument("--json", action="store_true", dest="json_output",
                        help="以 JSON 格式输出结果")
    parser.add_argument("--no-notify", action="store_true", help="跳过飞书通知")
    parser.add_argument("--env", default=None, help="运行环境: prod / test / ...")

    # 分离 pytest 额外参数（-- 后面的所有参数）
    argv = sys.argv[1:]
    extra_args = None
    if "--" in argv:
        idx = argv.index("--")
        extra_args = argv[idx + 1:]
        argv = argv[:idx]

    args = parser.parse_args(argv)

    env_name = args.env or os.environ.get("ENV", "prod")
    os.environ["ENV"] = env_name

    if args.list:
        modules = list_modules()
        if args.json_output:
            print(json.dumps(modules, ensure_ascii=False, indent=2))
        else:
            for biz_name, biz_info in modules.items():
                display = biz_info["display_name"]
                print(f"\n{'=' * 40}")
                print(f"  {display} ({biz_name})")
                print(f"{'=' * 40}")
                for type_name, type_modules in biz_info.get("test_modules", {}).items():
                    print(f"\n  {type_name.upper()} 测试模块:")
                    for mod_name, mod_desc in type_modules.items():
                        print(f"    {mod_name:15s} {mod_desc}")
        return 0

    targets = args.targets or ["all"]

    # 加载首个目标业务的 Settings 环境
    business, _, _ = _parse_target(targets[0])
    load_settings_for_business(business, env_name)

    if len(targets) == 1:
        result = run(targets[0], extra_args=extra_args)
    else:
        results = [run(t, extra_args=extra_args) for t in targets]
        result = {
            "returncode": max(r["returncode"] for r in results),
            "results": results,
        }

    if args.json_output:
        print(json.dumps(result, ensure_ascii=False, indent=2))

    if not args.no_notify:
        _send_feishu_notify(result.get("report_path", ""), business=business or "")

    return result.get("returncode", 1)


if __name__ == "__main__":
    sys.exit(main())
