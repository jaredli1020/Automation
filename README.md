# autotest - 通用自动化测试框架

基于 Playwright + Pytest + Requests + Django 的多业务自动化测试框架。支持 UI 自动化、接口自动化、定时调度、HTTP 触发、飞书通知、HTML 报告。

从 IdreamSky 创量测试平台抽象而来，去除业务耦合，可直接作为新项目的起点。

## 技术栈

- Python 3.10+
- Playwright（UI 自动化）
- Pytest（测试运行）
- Requests（接口测试）
- Django（HTTP 触发服务）
- schedule（定时任务）
- PyMySQL + sshtunnel（可选，数据库访问）

## 目录结构

```
automation_framework/
├── autotest/                       # 框架主包
│   ├── api/                        # 通用 API 客户端 + Auth + 断言
│   │   ├── client.py               # APIClient、APIResponse、thread-local 请求记录
│   │   ├── auth.py                 # AuthManager（token 缓存）
│   │   └── assertions.py
│   ├── core/                       # Playwright POM 基类
│   │   ├── base_page.py            # BasePage
│   │   └── base_component.py       # BaseComponent
│   ├── config/                     # BaseSettings 基类
│   │   └── base_settings.py
│   ├── db/                         # SSH 隧道 + MySQL 连接池（可选）
│   │   ├── connector.py            # JumpHostDatabaseConnector
│   │   └── connection_pool.py      # ConnectionPool + 隧道复用
│   ├── exceptions/                 # 自定义异常层级
│   ├── logging/                    # 日志（按天轮转 + 自动清理）
│   ├── utils/
│   │   ├── feishu.py               # 飞书卡片通知
│   │   ├── report_generator.py     # HTML 报告
│   │   ├── scheduler.py            # 定时任务调度
│   │   └── report_assets/          # 报告 CSS/JS（可覆盖）
│   ├── web/                        # Django HTTP 服务
│   │   ├── settings.py
│   │   ├── urls.py                 # /api/run、/api/jobs、/reports/ 等
│   │   └── views.py
│   ├── runner/                     # 多业务测试运行器
│   │   ├── runner.py               # run()、list_modules()、parse_target()
│   │   └── conftest_hooks.py       # pytest hooks（报告/截图/摘要）
│   └── fixtures/                   # 共享 pytest fixtures
│
├── demo/                           # 示例业务模块（可删除或复制作为模板）
│   ├── module.py                   # MODULE_CONFIG 注册
│   ├── config/settings.py          # 业务 Settings
│   ├── config/envs.py              # 环境字典
│   └── web/urls.py                 # 业务专属 Web 路由（可选）
│
├── tests/                          # 测试用例（按业务组织）
│   ├── conftest.py                 # 引入框架 hooks
│   └── demo/
│       ├── conftest.py             # demo 业务 fixtures
│       └── api/login/test_login.py
│
├── testdata/                       # 测试数据（按业务）
├── reports/                        # 测试报告（自动生成）
├── screenshots/                    # UI 失败截图（按业务隔离）
├── logs/                           # 日志
│
├── run_test.py                     # CLI 入口
├── server.py                       # HTTP 服务入口
├── schedule_config.yaml            # 定时任务配置
├── pytest.ini
├── requirements.txt
├── .env.example
└── .gitignore
```

## 快速开始

### 1. 安装依赖

```bash
python -m venv .venv
.venv\Scripts\activate    # Windows
source .venv/bin/activate # macOS / Linux

pip install -r requirements.txt
playwright install        # 仅 UI 测试需要
```

### 2. 配置环境变量

```bash
cp .env.example .env
# 按需修改 .env 里的 FEISHU_WEBHOOK_URL、DEMO_*_ACCOUNT 等
```

### 3. 运行示例

```bash
# 列出所有业务模块
python run_test.py --list

# 运行 demo 业务全部测试
python run_test.py demo

# 只跑 demo 接口测试
python run_test.py demo:api

# 只跑 demo 登录认证
python run_test.py demo:api:login

# 指定环境
python run_test.py --env test demo:api

# 跳过飞书通知
python run_test.py --no-notify demo:api

# 透传 pytest 参数
python run_test.py demo:api -- -k test_login -v
```

### 4. 启动 HTTP 服务

```bash
python server.py                   # 0.0.0.0:8000
python server.py --port 5000
```

内置接口：

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/run` | 触发测试，body: `{"business":"demo","type":"api","env":"prod"}` |
| GET  | `/api/jobs` | 任务列表（支持 `?status=running&business=demo`） |
| GET  | `/api/jobs/<job_id>` | 单个任务详情 |
| GET  | `/api/modules` | 列出所有业务模块 |
| GET  | `/api/schedule` | 查看定时任务配置 |
| GET  | `/api/health` | 健康检查 |
| GET  | `/reports/<file>` | 访问 HTML 报告 |

## 添加新业务模块

假设要添加一个 `shop` 业务：

### 1. 创建业务目录

```
shop/
├── __init__.py
├── module.py
├── config/
│   ├── __init__.py
│   ├── settings.py
│   └── envs.py
├── core/               # （UI 测试）业务专属页面对象基类
├── pages/              # （UI 测试）具体页面对象
├── components/         # （UI 测试）可复用组件
├── api/                # （接口测试）业务 API 客户端封装
└── web/urls.py         # （可选）业务专属 HTTP 路由
```

最简实现：复制 `demo/` 目录重命名为 `shop/`，改 `module.py` 中的 `name`、`display_name`、`test_modules` 即可。

### 2. 编写 MODULE_CONFIG

```python
# shop/module.py
MODULE_CONFIG = {
    "name": "shop",
    "display_name": "商城业务",
    "settings_class": "shop.config.settings.Settings",
    "test_modules": {
        "api": {"order": "订单接口", "product": "商品接口"},
        "ui": {"cart": "购物车"},
    },
    "report_module_names": {
        "api/order": "订单",
        "api/product": "商品",
        "ui/cart": "购物车",
    },
}
```

### 3. 编写 Settings

```python
# shop/config/settings.py
from autotest.config import BaseSettings
from .envs import ENVS

class Settings(BaseSettings):
    ENVS = ENVS
    API_LOGIN_PATH = "/api/auth/login"
```

```python
# shop/config/envs.py
ENVS = {
    "prod": {
        "API_BASE_URL": "https://api.shop.com",
        "TEST_ACCOUNT": "tester@shop.com",
        "TEST_PASSWORD": "xxxxx",
        "FEISHU_WEBHOOK_URL": "...",
    },
    "test": {
        "API_BASE_URL": "https://api-test.shop.com",
        "TEST_ACCOUNT": "tester@shop.com",
        "TEST_PASSWORD": "xxxxx",
    },
}
```

### 4. 注册业务

在 `run_test.py` 顶部的 `BUSINESS_MODULES` 列表中添加 `"shop"`：

```python
BUSINESS_MODULES = ["demo", "shop"]
register_modules(BUSINESS_MODULES)
```

### 5. 编写测试

```
tests/shop/
├── conftest.py          # 业务 fixtures（api_client 等）
├── api/
│   ├── order/test_*.py
│   └── product/test_*.py
└── ui/
    └── cart/test_*.py
```

`tests/shop/conftest.py` 可直接复制 `tests/demo/conftest.py` 并改 import。

### 6. 运行

```bash
python run_test.py shop:api
python run_test.py shop:api:order
python run_test.py shop:ui:cart
```

## 核心 API

### APIClient

```python
from autotest.api import APIClient, AuthManager, assert_success

token = AuthManager.login(settings_class=Settings)
client = APIClient.from_settings(Settings, token=token)

resp = client.post("/api/order/create", json={"product_id": 1})
assert_success(resp)
assert resp.data["order_id"]
```

### BasePage / BaseComponent

```python
from autotest.core import BasePage

class CartPage(BasePage):
    def add_item(self, product_name: str):
        self.safe_click(self.page.locator(f"text={product_name} >> .. >> button.add"))
        self.wait_for_visible(self.page.locator(".cart-count"))
```

### 数据库（可选）

```python
from autotest.db import create_db_config, JumpHostDatabaseConnector, get_pool

# 简单连接器（低频）
cfg = create_db_config(database_ip="10.0.0.1", database_name="orders")
db = JumpHostDatabaseConnector(cfg)
rows = db.query_params("SELECT * FROM orders WHERE id = %s", (123,))

# 连接池（高频/并发）
pool = get_pool(cfg)
with pool.connection() as conn:
    with conn.cursor() as c:
        c.execute("SELECT COUNT(*) FROM orders")
        count = c.fetchone()
```

### 飞书通知

业务 Settings 中配置 `FEISHU_WEBHOOK_URL`，测试结束后由 `conftest_hooks.py` 自动发送。也可手动调用：

```python
from autotest.utils import send_test_report
send_test_report(summary, report_path, webhook_url="...", report_title="商城接口测试")
```

### 日志

```python
from autotest.logging import get_logger
logger = get_logger(__name__)
logger.info("xxx")   # 输出到 logs/autotest_YYYY-MM-DD.log（按天轮转，默认保留 15 天）
```

## 定时任务

编辑 `schedule_config.yaml`：

```yaml
jobs:
  shop_api_daily:
    enabled: true
    time: "10:00"
    business: "shop"
    target: "api"
    env: "prod"
    notify: true
```

`python server.py` 启动时会自动读取并注册。也可直接运行：

```bash
python -m autotest.utils.scheduler            # 常驻调度
python -m autotest.utils.scheduler --run-now  # 立即执行所有启用任务
```

## 报告与输出目录

- `reports/` — HTML 报告 + 摘要 JSON + 趋势 JSON，超过 3 天的 `.html` / `.log` 会在下次运行时自动清理
- `screenshots/{business}/` — UI 失败时自动截图，按业务隔离
- `logs/` — 日志文件，按天轮转，自动清理过期文件

报告样式可通过覆盖 `autotest/utils/report_assets/` 下的 `report_style.css`、`report_script.js`、`report_logo.txt`（base64）进行定制。

## 向外扩展的关键点

| 场景 | 扩展方式 |
|------|----------|
| 新业务接入 | 新建 `{business}/module.py` + `config/settings.py`，在 `run_test.py` 注册 |
| 业务专属 Web 路由 | 在业务 `web/urls.py` 写 Django 路由，通过 django settings 的 `AUTOTEST_BUSINESS_URLS` 挂载 |
| 自定义报告样式 | 覆盖 `autotest/utils/report_assets/report_style.css` 等 |
| 自定义认证（非 email+md5） | `AuthManager.login(password_hash=False, token_key="access_token")`，或继承 `APIClient` 覆盖 `set_token` |
| 自定义数据库实例 | 在业务目录下建 `db.py`，用 `create_db_config()` + `JumpHostDatabaseConnector` 封装 |
| 共用 fixtures | 写到 `autotest/fixtures/` 或业务 `tests/{business}/conftest.py` |

## 约定

- 测试目录结构：`tests/{business}/{type}/{module}/test_*.py`
- 业务模块目录：`{business}/`，必须有 `module.py` 暴露 `MODULE_CONFIG`
- 测试数据：`testdata/{business}/...`
- 飞书通知避免重复：`run_test.py` 触发时设置 `_RUN_TEST_NOTIFY_HANDLED=1`，`conftest_hooks` 不再重复发送
- 摘要文件按业务隔离：`reports/test_summary_{business}.json`，避免多业务并行时互相覆盖

## 许可

根据业务项目需要自行添加 LICENSE。
