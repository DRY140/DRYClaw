from __future__ import annotations

import json
from typing import Any

from dryclaw.config.config import load_config
from dryclaw.tools.axserver import AXServerClient


class WaitForTool:
    name = "wait_for"
    description = "Wait until UI condition becomes true via ax_server wait_for"
    input_schema = {
        "type": "object",
        "properties": {
            "condition": {
                "type": "string",
                "description": "elementExists|elementGone|titleContains|urlContains|titleChanged|urlChanged",
            },
            "pid": {"type": "integer", "description": "Target app pid", "default": 0},
            "query": {"type": "string", "description": "query for element wait", "default": ""},
            "role": {"type": "string", "description": "role for element wait", "default": ""},
            "value": {"type": "string", "description": "contains value", "default": ""},
            "timeout": {"type": "number", "description": "seconds", "default": 10},
            "interval": {"type": "number", "description": "polling interval", "default": 0.5},
        },
        "required": ["condition"],
    }

    def __init__(self, client: AXServerClient | None = None) -> None:
        cfg = load_config()
        self.client = client or AXServerClient(
            cfg.ax_server_path,
            mode=cfg.ax_server_mode,
            socket_path=cfg.ax_server_socket_path,
        )

    @staticmethod
    def _condition_alias(value: str) -> str:
        raw = value.strip()
        alias = {
            "element_exists": "elementExists",
            "element_gone": "elementGone",
            "element_text_contains": "elementExists",
            "window_title_equals": "titleContains",
            "title_contains": "titleContains",
            "url_contains": "urlContains",
            "title_changed": "titleChanged",
            "url_changed": "urlChanged",
        }
        return alias.get(raw.lower(), raw)

    def run(self, **kwargs: Any) -> str:
        condition = self._condition_alias(str(kwargs.get("condition", "")))
        timeout = float(kwargs.get("timeout", 10) or 10)
        interval = float(kwargs.get("interval", 0.5) or 0.5)

        params = {
            "condition": condition,
            "pid": kwargs.get("pid"),
            "query": kwargs.get("query", kwargs.get("selector", "")),
            "role": kwargs.get("role", ""),
            "value": kwargs.get("value", kwargs.get("text", kwargs.get("title", ""))),
            "timeout": timeout,
            "interval": interval,
        }
        params = {k: v for k, v in params.items() if v not in (None, "")}
        resp = self.client.send_command("wait_for", params, timeout=timeout + 2.0)
        return json.dumps(resp, ensure_ascii=False)
