#!/usr/bin/env python
"""HTTP 测试服务入口 - Django + 定时任务

启动后同时运行：
  - Django HTTP 服务（测试触发、任务管理、报告托管）
  - schedule 定时任务后台线程

用法:
  python server.py                # 默认 0.0.0.0:8000
  python server.py --port 5000
"""

import os
import sys
import threading
import argparse
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.resolve()
sys.path.insert(0, str(PROJECT_ROOT))
os.environ.setdefault("PROJECT_ROOT", str(PROJECT_ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "autotest.web.settings")


def start_scheduler():
    """在后台线程中启动定时任务"""
    import time
    import schedule as schedule_lib
    from autotest.utils.scheduler import load_config, execute_job

    try:
        config = load_config()
    except SystemExit:
        print("[调度器] 未找到 schedule_config.yaml，跳过定时任务")
        return

    jobs = config.get("jobs", {})
    for name, cfg in jobs.items():
        if not cfg.get("enabled", True):
            continue
        run_time = cfg.get("time")
        if not run_time:
            continue
        schedule_lib.every().day.at(run_time).do(execute_job, name, cfg).tag(name)
        business = cfg.get("business", "")
        print(f"[调度器] 已注册: {name} -> 每天 {run_time} | 业务: {business} | 目标: {cfg.get('target')}")

    print("[调度器] 定时任务已启动")

    while True:
        schedule_lib.run_pending()
        time.sleep(30)


def main():
    parser = argparse.ArgumentParser(description="自动化测试 HTTP 服务")
    parser.add_argument("--port", type=int, default=8000, help="端口（默认 8000）")
    parser.add_argument("--host", default="0.0.0.0", help="监听地址（默认 0.0.0.0）")
    args = parser.parse_args()

    import django
    django.setup()

    scheduler_thread = threading.Thread(target=start_scheduler, daemon=True)
    scheduler_thread.start()

    from django.core.management import call_command
    print(f"[服务器] 启动 HTTP 服务 http://{args.host}:{args.port}")
    call_command("runserver", f"{args.host}:{args.port}", "--noreload")


if __name__ == "__main__":
    main()
