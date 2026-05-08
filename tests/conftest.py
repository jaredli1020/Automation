"""全局 pytest conftest - 引入框架通用 hooks

业务模块的专属 fixtures 在各自 tests/{business}/conftest.py 中定义。
"""

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(PROJECT_ROOT))
os.environ.setdefault("PROJECT_ROOT", str(PROJECT_ROOT))

from autotest.runner.conftest_hooks import *  # noqa: F401, F403
