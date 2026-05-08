"""demo 业务模块注册描述符

框架通过 module.py 的 MODULE_CONFIG 动态发现业务模块。
"""

MODULE_CONFIG = {
    "name": "demo",
    "display_name": "示例业务",
    "settings_class": "demo.config.settings.Settings",
    "web_urls": "demo.web.urls",
    "test_modules": {
        "api": {
            "login": "登录认证测试",
        },
        "ui": {
            "home": "首页测试",
        },
    },
    "report_module_names": {
        "api/login": "登录认证",
        "ui/home": "首页",
    },
}
