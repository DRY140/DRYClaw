from __future__ import annotations

import threading
from dataclasses import dataclass


@dataclass
class _BrowserState:
    playwright: object | None = None
    browser: object | None = None
    context: object | None = None
    page: object | None = None


class BrowserTool:
    name = "browser"
    description = "Navigate and interact with browser pages via Playwright"
    input_schema = {
        "type": "object",
        "properties": {
            "action": {"type": "string", "description": "navigate|click|get_text"},
            "url": {"type": "string", "description": "Target URL"},
            "selector": {"type": "string", "description": "CSS selector"},
        },
        "required": ["action"],
    }

    def __init__(self) -> None:
        self._state = _BrowserState()
        self._lock = threading.Lock()

    def run(self, **kwargs) -> str:
        action = str(kwargs.get("action", "")).strip().lower()
        url = str(kwargs.get("url", "")).strip()
        selector = str(kwargs.get("selector", "")).strip()

        if action not in {"navigate", "click", "get_text"}:
            return "ERROR: action must be navigate|click|get_text"

        try:
            with self._lock:
                self._ensure_browser()
                page = self._state.page
                assert page is not None

                if action == "navigate":
                    if not url:
                        return "ERROR: missing url"
                    page.goto(url, timeout=30_000, wait_until="domcontentloaded")
                    text = page.inner_text("body")
                    return text[:50_000]

                if action == "click":
                    if not selector:
                        return "ERROR: missing selector"
                    page.click(selector, timeout=30_000)
                    return "OK: clicked"

                if not selector:
                    return "ERROR: missing selector"
                text = page.inner_text(selector, timeout=30_000)
                return text[:50_000]
        except Exception as exc:
            return f"ERROR: browser failed: {exc}"

    def _ensure_browser(self) -> None:
        if self._state.page is not None:
            return

        try:
            from playwright.sync_api import sync_playwright
        except Exception as exc:
            raise RuntimeError(f"playwright unavailable: {exc}")

        self._state.playwright = sync_playwright().start()
        self._state.browser = self._state.playwright.chromium.launch(headless=True)
        self._state.context = self._state.browser.new_context()
        self._state.page = self._state.context.new_page()
