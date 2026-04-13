from __future__ import annotations

import json
import time
from typing import Any

from dryclaw.config.config import load_config
from dryclaw.tools.axserver import AXServerClient


class AccessibilityTool:
    name = "accessibility"
    description = "Read and interact with macOS accessibility elements via ax_server"
    input_schema = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "description": "read_tree|click|press|set_value|get_value|find|scroll|annotate|frontmost|focus|list_windows|wait_for",
            },
            "pid": {"type": "integer", "description": "Target app pid", "default": 0},
            "app_name": {"type": "string", "description": "Target app name", "default": ""},
            "path": {"type": "string", "description": "Element path/ref", "default": ""},
            "expected_role": {"type": "string", "description": "Expected role", "default": ""},
            "value": {"type": "string", "description": "value/text", "default": ""},
            "query": {"type": "string", "description": "find query", "default": ""},
            "role": {"type": "string", "description": "find role", "default": ""},
            "identifier": {"type": "string", "description": "find identifier", "default": ""},
            "dx": {"type": "integer", "description": "scroll dx", "default": 0},
            "dy": {"type": "integer", "description": "scroll dy", "default": 0},
            "condition": {"type": "string", "description": "wait_for condition", "default": ""},
            "timeout": {"type": "number", "description": "wait timeout seconds", "default": 10},
            "interval": {"type": "number", "description": "wait poll interval", "default": 0.5},
            "roles": {"type": "array", "items": {"type": "string"}, "description": "annotate roles", "default": []},
            "max_labels": {"type": "integer", "description": "annotate max labels", "default": 50},
            "window_title": {"type": "string", "description": "focus window title", "default": ""},
            "verify": {"type": "boolean", "description": "focus verify", "default": False},
        },
        "required": ["action"],
    }

    def __init__(self, client: AXServerClient | None = None) -> None:
        cfg = load_config()
        self.client = client or AXServerClient(
            cfg.ax_server_path,
            mode=cfg.ax_server_mode,
            socket_path=cfg.ax_server_socket_path,
        )

    @staticmethod
    def _clean_params(raw: dict[str, Any]) -> dict[str, Any]:
        return {k: v for k, v in raw.items() if v not in (None, "", [], {})}

    def run(self, **kwargs: Any) -> str:
        action = str(kwargs.get("action", "")).strip().lower()

        # Backward-compat aliases.
        if action == "get_elements":
            action = "read_tree"
        if action == "click_element":
            action = "click"
        if action == "type_text" and kwargs.get("path"):
            action = "set_value"

        pid = kwargs.get("pid")
        app_name = str(kwargs.get("app_name", kwargs.get("app", ""))).strip()
        path = str(kwargs.get("path", kwargs.get("ref", ""))).strip()
        value = str(kwargs.get("value", kwargs.get("text", "")))

        if action == "read_tree":
            params = self._clean_params({"pid": pid})
            if not params and app_name:
                resolved = self.client.send_command("resolve_pid", {"app_name": app_name})
                if resolved.get("ok") and resolved.get("pid"):
                    params["pid"] = resolved.get("pid")
            resp = self.client.send_command("read_tree", params)

            # 多桌面场景下目标 app 不在当前可见桌面时，先尝试 focus 再重试一次。
            if not resp.get("ok") and "No windows found" in str(resp.get("error", "")):
                focus_params = self._clean_params({"app_name": app_name, "pid": pid})
                if focus_params:
                    self.client.send_command("focus", focus_params)
                    time.sleep(1.5)
                    resp = self.client.send_command("read_tree", params)

            return json.dumps(resp, ensure_ascii=False)

        if action in {"click", "press"}:
            if not path:
                return "ERROR: missing path/ref"
            params = self._clean_params(
                {
                    "pid": pid,
                    "path": path,
                    "expected_role": kwargs.get("expected_role"),
                }
            )
            resp = self.client.send_command(action, params)
            return json.dumps(resp, ensure_ascii=False)

        if action == "set_value":
            if not path:
                return "ERROR: missing path/ref"
            params = self._clean_params(
                {
                    "pid": pid,
                    "path": path,
                    "value": value,
                    "expected_role": kwargs.get("expected_role"),
                }
            )
            resp = self.client.send_command("set_value", params)
            return json.dumps(resp, ensure_ascii=False)

        if action == "get_value":
            if not path:
                return "ERROR: missing path/ref"
            params = self._clean_params({"pid": pid, "path": path})
            resp = self.client.send_command("get_value", params)
            return json.dumps(resp, ensure_ascii=False)

        if action == "find":
            params = self._clean_params(
                {
                    "pid": pid,
                    "query": kwargs.get("query"),
                    "role": kwargs.get("role"),
                    "identifier": kwargs.get("identifier"),
                }
            )
            resp = self.client.send_command("find", params)
            return json.dumps(resp, ensure_ascii=False)

        if action == "scroll":
            params = self._clean_params(
                {
                    "pid": pid,
                    "path": path,
                    "dx": kwargs.get("dx", 0),
                    "dy": kwargs.get("dy", 0),
                }
            )
            resp = self.client.send_command("scroll", params)
            return json.dumps(resp, ensure_ascii=False)

        if action == "annotate":
            params = self._clean_params(
                {
                    "pid": pid,
                    "roles": kwargs.get("roles"),
                    "max_labels": kwargs.get("max_labels", 50),
                }
            )
            resp = self.client.send_command("annotate", params)
            return json.dumps(resp, ensure_ascii=False)

        if action == "frontmost":
            resp = self.client.send_command("frontmost", {})
            return json.dumps(resp, ensure_ascii=False)

        if action == "focus":
            if not app_name:
                return "ERROR: missing app_name"
            params = self._clean_params(
                {
                    "app_name": app_name,
                    "window_title": kwargs.get("window_title"),
                    "verify": kwargs.get("verify", False),
                }
            )
            resp = self.client.send_command("focus", params)
            return json.dumps(resp, ensure_ascii=False)

        if action == "list_windows":
            params = self._clean_params({"pid": pid})
            resp = self.client.send_command("list_windows", params)
            return json.dumps(resp, ensure_ascii=False)

        if action == "wait_for":
            params = self._clean_params(
                {
                    "pid": pid,
                    "condition": kwargs.get("condition"),
                    "value": kwargs.get("value"),
                    "query": kwargs.get("query"),
                    "role": kwargs.get("role"),
                    "timeout": kwargs.get("timeout", 10),
                    "interval": kwargs.get("interval", 0.5),
                }
            )
            resp = self.client.send_command("wait_for", params, timeout=float(kwargs.get("timeout", 10)) + 2.0)
            return json.dumps(resp, ensure_ascii=False)

        return "ERROR: unsupported action"
