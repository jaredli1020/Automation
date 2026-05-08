"""定时测试调度器 - 通用版本，支持多业务模块

读取 schedule_config.yaml 配置，按设定时间自动执行测试任务。
执行时动态导入项目根目录的 run_test 模块（由业务项目提供）。
"""

import sys
import os
import time
import yaml
import schedule
import logging
import importlib
from pathlib import Path


def _setup_logger(log_dir: Path = None):
    log_dir = log_dir or Path(os.getenv("LOG_DIR", "logs"))
    log_dir.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger("autotest.scheduler")
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    fmt = logging.Formatter(
        "%(asctime)s [调度器] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    console = logging.StreamHandler()
    console.setFormatter(fmt)
    logger.addHandler(console)
    file_handler = logging.FileHandler(log_dir / "scheduler.log", encoding="utf-8")
    file_handler.setFormatter(fmt)
    logger.addHandler(file_handler)
    return logger


log = _setup_logger()


def load_config(config_path: Path = None) -> dict:
    """加载定时任务配置

    默认路径：<PROJECT_ROOT>/schedule_config.yaml，也可通过
    AUTOTEST_SCHEDULE_CONFIG 环境变量指定。
    """
    if config_path is None:
        env_path = os.getenv("AUTOTEST_SCHEDULE_CONFIG")
        if env_path:
            config_path = Path(env_path)
        else:
            config_path = Path.cwd() / "schedule_config.yaml"

    if not config_path.exists():
        log.error(f"配置文件不存在: {config_path}")
        sys.exit(1)
    with open(config_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data or {"jobs": {}}


def _load_runner():
    """动态加载项目根目录的 run_test 模块"""
    project_root = Path(os.getenv("PROJECT_ROOT", Path.cwd()))
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    return importlib.import_module("run_test")


def execute_job(job_name: str, job_config: dict):
    """执行单个定时测试任务"""
    target = job_config.get("target", "all")
    env_name = job_config.get("env", "prod")
    business = job_config.get("business", "")

    log.info("=" * 50)
    log.info(f"开始执行: {job_name} | 业务: {business} | 目标: {target} | 环境: {env_name}")
    log.info("=" * 50)

    try:
        os.environ["ENV"] = env_name

        runner = _load_runner()

        full_target = f"{business}:{target}" if business else target
        result = runner.run(target=full_target)

        returncode = result.get("returncode", 1)
        report_path = result.get("report_path", "")
        log.info(f"{job_name} 执行完毕 | returncode={returncode} | 报告: {report_path}")

        if job_config.get("notify", True) and hasattr(runner, "_send_feishu_notify"):
            runner._send_feishu_notify(report_path, business=business)

    except Exception as e:
        log.error(f"{job_name} 执行异常: {e}", exc_info=True)


def register_jobs(config: dict) -> int:
    """注册所有定时任务，返回已注册的任务数量"""
    jobs = config.get("jobs", {})
    if not jobs:
        log.warning("未配置任何任务")
        return 0

    count = 0
    for name, cfg in jobs.items():
        if not cfg.get("enabled", True):
            log.info(f"跳过已禁用任务: {name}")
            continue

        run_time = cfg.get("time")
        if not run_time:
            log.warning(f"任务 {name} 未配置 time，跳过")
            continue

        schedule.every().day.at(run_time).do(execute_job, name, cfg).tag(name)
        business = cfg.get("business", "")
        log.info(
            f"已注册: {name} -> 每天 {run_time} | 业务: {business} | "
            f"目标: {cfg.get('target')} | 环境: {cfg.get('env', 'prod')}"
        )
        count += 1

    return count


def run_all_now(config: dict):
    """立即执行所有已启用任务"""
    jobs = config.get("jobs", {})
    for name, cfg in jobs.items():
        if cfg.get("enabled", True):
            execute_job(name, cfg)


def main():
    config = load_config()

    if "--run-now" in sys.argv:
        log.info("立即执行模式")
        run_all_now(config)
        return

    count = register_jobs(config)
    if count == 0:
        log.warning("没有可执行的任务，退出")
        return

    log.info(f"调度器已启动，共 {count} 个任务，按 Ctrl+C 停止")

    try:
        while True:
            schedule.run_pending()
            time.sleep(30)
    except KeyboardInterrupt:
        log.info("调度器已停止")


if __name__ == "__main__":
    main()
