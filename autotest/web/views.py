"""通用 HTTP 测试触发接口 - 参数化，支持多业务模块

业务项目通过在 settings.py 中配置 AUTOTEST_BUSINESS_URLS 来 include
自己的业务路由（可选）。核心接口由本模块提供。
"""

import json
import os
import dataclasses
import threading
import importlib
import random
import string
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST, require_GET


@dataclasses.dataclass
class JobInfo:
    job_id: str
    business: str
    type: str
    env: str
    status: str          # queued / running / completed / failed
    trigger: str         # api / schedule
    notify: bool
    created_at: str
    started_at: str = ""
    finished_at: str = ""
    returncode: int = -1
    report_path: str = ""
    error: str = ""


_jobs: dict[str, JobInfo] = {}
_jobs_lock = threading.Lock()
_executor = ThreadPoolExecutor(max_workers=1)

MAX_JOBS = 100


def _cleanup_old_jobs():
    if len(_jobs) <= MAX_JOBS:
        return
    finished = sorted(
        [j for j in _jobs.values() if j.status in ("completed", "failed")],
        key=lambda j: j.created_at,
    )
    while len(_jobs) > MAX_JOBS and finished:
        old = finished.pop(0)
        _jobs.pop(old.job_id, None)


def _to_report_url(report_path: str) -> str:
    if not report_path or report_path.startswith("http"):
        return report_path
    base_url = os.environ.get("REPORT_BASE_URL", "http://localhost:8000").rstrip("/")
    filename = Path(report_path).name
    return f"{base_url}/reports/{filename}"


def _load_runner():
    """动态加载项目根目录的 run_test 模块"""
    project_root = Path(os.environ.get("PROJECT_ROOT", Path.cwd()))
    import sys
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    return importlib.import_module("run_test")


def _execute_test(job_id: str, business: str, test_type: str, env: str, notify: bool, trigger: str):
    job = _jobs.get(job_id)
    if not job:
        return

    job.status = "running"
    job.started_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    try:
        os.environ["ENV"] = env

        # 加载对应业务的 Settings（若存在）
        try:
            settings_mod = importlib.import_module(f"{business}.config.settings")
            settings_cls = getattr(settings_mod, "Settings")
            settings_cls.load_env(env)
        except (ImportError, AttributeError):
            pass

        runner = _load_runner()
        target = f"{business}:{test_type}" if business else test_type
        result = runner.run(target=target)

        job.returncode = result.get("returncode", 1)
        job.report_path = _to_report_url(result.get("report_path", ""))
        job.status = "completed" if job.returncode == 0 else "failed"

        if notify and hasattr(runner, "_send_feishu_notify"):
            runner._send_feishu_notify(job.report_path, business=business)

    except Exception as e:
        job.status = "failed"
        job.error = str(e)

    finally:
        job.finished_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def submit_test(business: str, test_type: str, env: str,
                notify: bool = True, trigger: str = "api") -> JobInfo:
    suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=4))
    job_id = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{suffix}"

    job = JobInfo(
        job_id=job_id,
        business=business,
        type=test_type,
        env=env,
        status="queued",
        trigger=trigger,
        notify=notify,
        created_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    )

    with _jobs_lock:
        _jobs[job_id] = job
        _cleanup_old_jobs()

    _executor.submit(_execute_test, job_id, business, test_type, env, notify, trigger)
    return job


# ==================== 接口视图 ====================

def _ok(data=None, message="ok"):
    return JsonResponse({"code": 0, "message": message, "data": data})


def _error(message, code=1, status=400):
    return JsonResponse({"code": code, "message": message, "data": None}, status=status)


@csrf_exempt
@require_POST
def run_test(request):
    """触发测试

    POST /api/run
    Body: {"business": "demo", "type": "api"|"ui", "env": "prod"|"test", "notify": true}
    """
    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return _error("请求体必须是 JSON 格式")

    business = body.get("business", "")
    test_type = body.get("type")
    env = body.get("env")

    if test_type not in ("api", "ui"):
        return _error("type 参数必须是 api 或 ui")
    if not env:
        return _error("env 参数不能为空")

    notify = body.get("notify", True)
    job = submit_test(business, test_type, env, notify=notify, trigger="api")
    return _ok(data=dataclasses.asdict(job), message="测试任务已提交")


@require_GET
def get_jobs(request):
    """查询任务列表"""
    status_filter = request.GET.get("status")
    business_filter = request.GET.get("business")
    with _jobs_lock:
        jobs = list(_jobs.values())

    if status_filter:
        jobs = [j for j in jobs if j.status == status_filter]
    if business_filter:
        jobs = [j for j in jobs if j.business == business_filter]

    jobs.sort(key=lambda j: j.created_at, reverse=True)
    return _ok(data=[dataclasses.asdict(j) for j in jobs[:50]])


@require_GET
def get_job(request, job_id):
    """查询单个任务"""
    job = _jobs.get(job_id)
    if not job:
        return _error("任务不存在", status=404)
    return _ok(data=dataclasses.asdict(job))


@require_GET
def get_modules(request):
    """列出可用测试模块（委托给 run_test.list_modules）"""
    try:
        runner = _load_runner()
        return _ok(data=runner.list_modules())
    except Exception as e:
        return _error(f"加载业务模块失败: {e}")


@require_GET
def get_schedule(request):
    """查看定时任务配置"""
    try:
        from autotest.utils.scheduler import load_config
        config = load_config()
        return _ok(data=config.get("jobs", {}))
    except SystemExit:
        return _ok(data={}, message="未配置定时任务")


@require_GET
def health(request):
    """健康检查"""
    return _ok(data={"status": "running", "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")})
