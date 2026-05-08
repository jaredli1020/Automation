"""组件基类，用于可复用的 UI 组件（弹窗、对话框等）"""

from playwright.sync_api import Page, Locator


class BaseComponent:
    """UI 组件的基类。子类必须实现 root_locator 定位组件根节点。"""

    def __init__(self, page: Page, timeout: int = 10000, short_timeout: int = 3000):
        self.page = page
        self.timeout = timeout
        self.short_timeout = short_timeout

    @property
    def root_locator(self) -> Locator:
        raise NotImplementedError("子类必须实现 root_locator")

    def is_visible(self, timeout: int = None) -> bool:
        timeout = timeout or self.short_timeout
        try:
            self.root_locator.wait_for(state="visible", timeout=timeout)
            return True
        except Exception:
            return False

    def wait_for_visible(self, timeout: int = None):
        timeout = timeout or self.timeout
        self.root_locator.wait_for(state="visible", timeout=timeout)

    def wait_for_hidden(self, timeout: int = None):
        timeout = timeout or self.timeout
        self.root_locator.wait_for(state="hidden", timeout=timeout)

    def close(self):
        """默认尝试点击组件内的关闭按钮"""
        close_btn = self.root_locator.locator("[class*='close']").first
        if close_btn.is_visible():
            close_btn.click()
            self.wait_for_hidden()

    def _locator(self, selector: str) -> Locator:
        """获取相对于组件根元素的定位器"""
        return self.root_locator.locator(selector)

    def _safe_click(self, locator: Locator, timeout: int = None):
        timeout = timeout or self.timeout
        locator.wait_for(state="visible", timeout=timeout)
        locator.click()

    def _safe_fill(self, locator: Locator, text: str, timeout: int = None):
        timeout = timeout or self.timeout
        locator.wait_for(state="visible", timeout=timeout)
        locator.fill(text)

    def _get_text(self, locator: Locator) -> str:
        return locator.text_content() or ""
