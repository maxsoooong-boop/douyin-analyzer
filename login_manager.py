# -*- coding: utf-8 -*-
"""抖音登录管理：弹出浏览器窗口让用户扫码登录，登录后自动提取 Cookie。"""
import threading
import time
import logging
from typing import Optional, Dict, Any

from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page

logger = logging.getLogger("login")


class LoginManager:
    def __init__(self):
        self._lock = threading.Lock()
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None
        self._playwright = None
        self.status: str = "idle"  # idle / opening / waiting_login / success / failed
        self.cookie: str = ""
        self.error: str = ""
        self._login_thread: Optional[threading.Thread] = None

    def start_login(self):
        """启动登录流程：弹出 Chrome 窗口打开抖音登录页，后台线程轮询登录状态。"""
        with self._lock:
            if self.status in ("opening", "waiting_login"):
                return  # 已经在登录流程中
            # 如果之前有浏览器，先关掉
            self._close_browser()
            self.status = "opening"
            self.cookie = ""
            self.error = ""

        self._login_thread = threading.Thread(target=self._run_login, daemon=True)
        self._login_thread.start()

    def _run_login(self):
        try:
            self._playwright = sync_playwright().start()
            # 用有头模式，让用户能看到登录窗口并扫码
            self._browser = self._playwright.chromium.launch(
                channel="chrome",
                headless=False,
                args=["--start-maximized"],
            )
            self._context = self._browser.new_context(
                viewport=None,
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
            )
            self._page = self._context.new_page()
            self._page.goto("https://www.douyin.com/", wait_until="domcontentloaded")
            self.status = "waiting_login"
            logger.info("登录窗口已打开，等待用户扫码登录...")

            # 轮询检测登录状态：最多等 120 秒
            for i in range(120):
                time.sleep(1)
                try:
                    # 检测页面上是否出现"登录"按钮——如果消失了说明登录成功
                    login_btn = self._page.query_selector('button:has-text("登录")')
                    if not login_btn:
                        # 再等 2 秒让 cookie 稳定
                        time.sleep(2)
                        # 提取所有 cookie
                        cookies = self._context.cookies("https://www.douyin.com")
                        if cookies:
                            self.cookie = "; ".join([f"{c['name']}={c['value']}" for c in cookies])
                            self.status = "success"
                            logger.info("登录成功，提取到 %d 个 Cookie", len(cookies))
                            # 登录成功后关掉浏览器窗口
                            self._close_browser()
                            return
                except Exception as e:
                    logger.debug("轮询检测登录状态出错: %s", e)
                    continue

            # 超时
            self.status = "failed"
            self.error = "登录超时（120秒内未检测到登录成功）"
            self._close_browser()

        except Exception as e:
            self.status = "failed"
            self.error = f"启动登录窗口失败: {str(e)}"
            logger.exception("登录流程出错")
            self._close_browser()

    def get_status(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "cookie_ready": bool(self.cookie),
            "error": self.error,
        }

    def get_cookie(self) -> str:
        return self.cookie

    def _close_browser(self):
        try:
            if self._browser:
                self._browser.close()
        except Exception:
            pass
        try:
            if self._playwright:
                self._playwright.stop()
        except Exception:
            pass
        self._browser = None
        self._context = None
        self._page = None
        self._playwright = None


# 全局单例
login_manager = LoginManager()
