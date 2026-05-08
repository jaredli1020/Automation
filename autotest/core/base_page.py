"""页面基类，提供通用 Playwright 操作"""

from playwright.sync_api import Page, Locator


class BasePage:
    """所有页面对象的基类。超时配置通过构造函数注入，便于各业务覆盖默认值。"""

    def __init__(self, page: Page, timeout: int = 10000,
                 short_timeout: int = 3000, long_timeout: int = 30000,
                 screenshots_dir=None):
        self.page = page
        self.timeout = timeout
        self.short_timeout = short_timeout
        self.long_timeout = long_timeout
        self._screenshots_dir = screenshots_dir

    def wait_for_visible(self, locator: Locator, timeout: int = None) -> Locator:
        timeout = timeout or self.timeout
        locator.wait_for(state="visible", timeout=timeout)
        return locator

    def wait_for_hidden(self, locator: Locator, timeout: int = None):
        timeout = timeout or self.timeout
        locator.wait_for(state="hidden", timeout=timeout)

    def safe_click(self, locator: Locator, timeout: int = None):
        timeout = timeout or self.timeout
        locator.wait_for(state="visible", timeout=timeout)
        locator.click()

    def safe_fill(self, locator: Locator, text: str, timeout: int = None):
        timeout = timeout or self.timeout
        locator.wait_for(state="visible", timeout=timeout)
        locator.fill(text)

    def safe_hover(self, locator: Locator, timeout: int = None):
        timeout = timeout or self.timeout
        locator.wait_for(state="visible", timeout=timeout)
        locator.hover()

    def safe_drag_to(self, source: Locator, target: Locator, timeout: int = None):
        timeout = timeout or self.timeout
        source.wait_for(state="visible", timeout=timeout)
        target.wait_for(state="visible", timeout=timeout)
        source.drag_to(target)

    def is_visible(self, locator: Locator, timeout: int = None) -> bool:
        timeout = timeout or self.short_timeout
        try:
            locator.wait_for(state="visible", timeout=timeout)
            return True
        except Exception:
            return False

    def get_text(self, locator: Locator, timeout: int = None) -> str:
        timeout = timeout or self.timeout
        locator.wait_for(state="visible", timeout=timeout)
        return locator.text_content() or ""

    def get_count(self, locator: Locator) -> int:
        return locator.count()

    def has_dialog(self) -> bool:
        """检查是否存在通用弹窗（Ant Design / ElementUI / 通用）"""
        dialog_selectors = [
            "[role='dialog']",
            ".ant-modal",
            ".el-dialog",
            "[class*='dialog']",
            "[class*='modal']",
        ]
        for selector in dialog_selectors:
            if self.page.locator(selector).count() > 0:
                try:
                    if self.page.locator(selector).first.is_visible():
                        return True
                except Exception:
                    pass
        return False

    def close_dialog_if_exists(self) -> bool:
        """若存在弹窗则关闭，返回是否成功关闭"""
        close_selectors = [
            "[role='dialog'] [class*='close']",
            ".ant-modal-close",
            ".el-dialog__close",
            "[class*='dialog'] [class*='close']",
        ]
        for selector in close_selectors:
            locator = self.page.locator(selector).first
            if self.is_visible(locator, timeout=1000):
                locator.click()
                return True
        return False

    def screenshot(self, name: str, timeout: int = 10000) -> str:
        """截图并返回保存路径"""
        if self._screenshots_dir:
            self._screenshots_dir.mkdir(parents=True, exist_ok=True)
            path = self._screenshots_dir / f"{name}.png"
        else:
            path = f"{name}.png"
        try:
            self.page.screenshot(path=str(path), timeout=timeout)
        except Exception as e:
            print(f"截图失败: {e}")
        return str(path)

    def press_key(self, key: str):
        self.page.keyboard.press(key)

    def wait_for_load(self, timeout: int = None):
        timeout = timeout or self.long_timeout
        self.page.wait_for_load_state("domcontentloaded", timeout=timeout)
