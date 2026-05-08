"""demo 业务多环境配置"""

import os

ENVS = {
    "prod": {
        "API_BASE_URL": os.environ.get("DEMO_PROD_API_BASE_URL", "https://api.example.com"),
        "API_HOST_IP": "",
        "TEST_ACCOUNT": os.environ.get("DEMO_PROD_ACCOUNT", ""),
        "TEST_PASSWORD": os.environ.get("DEMO_PROD_PASSWORD", ""),
        "FEISHU_WEBHOOK_URL": os.environ.get("DEMO_PROD_FEISHU_WEBHOOK_URL", ""),
    },
    "test": {
        "API_BASE_URL": os.environ.get("DEMO_TEST_API_BASE_URL", "https://api-test.example.com"),
        "API_HOST_IP": "",
        "TEST_ACCOUNT": os.environ.get("DEMO_TEST_ACCOUNT", ""),
        "TEST_PASSWORD": os.environ.get("DEMO_TEST_PASSWORD", ""),
        "FEISHU_WEBHOOK_URL": os.environ.get("DEMO_TEST_FEISHU_WEBHOOK_URL", ""),
    },
}
