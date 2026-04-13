from __future__ import annotations

import json
from typing import Any

from dryclaw.config.config import load_config
from dryclaw.tools.axserver import AXServerClient
from dryclaw.tools.screenshot import ScreenshotTool


class ComputerTool:
    name = "computer"
    description = "Fallback mouse/keyboard control via ax_server"
    input_schema = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "description": "click|double_click|right_click|move|hotkey|key|type|scroll|screenshot",
            },
            "x": {"type": "integer", "description": "x", "default": 0},
            "y": {"type": "integer", "description": "y", "default": 0},
            "text": {"type": "string", "description": "typing text", "default": ""},
            "key_combination": {"type": "string", "description": "shortcut", "default": ""},
            "direction": {"type": "string", "description": "up|down", "default": "down"},
            "amount": {"type": "integer", "description": "scroll amount", "default": 1},
            "dx": {"type": "integer", "description": "scroll dx", "default": 0},
            "dy": {"type": "integer", "description": "scroll dy", "default": 0},
            "button": {"type": "string", "description": "left|right|center", "default": "left"},
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
        self.screenshot = ScreenshotTool()

    @staticmethod
    def _parse_hotkey(text: str) -> tuple[str, list[str]]:
        raw = [part.strip().lower() for part in text.split("+") if part.strip()]
        if not raw:
            return "", []
        key = raw[-1]
        modifiers = []
        for part in raw[:-1]:
            if part in {"cmd", "command", "meta"}:
                modifiers.append("cmd")
            elif part in {"ctrl", "control"}:
                modifiers.append("ctrl")
            elif part in {"opt", "option", "alt"}:
                modifiers.append("alt")
            elif part == "shift":
                modifiers.append("shift")
        return key, modifiers

    def run(self, **kwargs: Any) -> str:
        action = str(kwargs.get("action", "")).strip().lower()
        if action == "screenshot":
            return self.screenshot.run(**kwargs)

        if action in {"click", "double_click", "right_click", "move"}:
            clicks = 2 if action == "double_click" else 1
            button = "right" if action == "right_click" else str(kwargs.get("button", "left"))
            mouse_type = "move" if action == "move" else "click"
            params = {
                "type": mouse_type,
                "x": kwargs.get("x"),
                "y": kwargs.get("y"),
                "button": button,
                "clicks": clicks,
            }
            params = {k: v for k, v in params.items() if v is not None}
            resp = self.client.send_command("mouse_event", params)
            return json.dumps(resp, ensure_ascii=False)

        if action in {"hotkey", "key"}:
            key_text = str(kwargs.get("key_combination", kwargs.get("key", ""))).strip()
            key, modifiers = self._parse_hotkey(key_text)
            if not key:
                return "ERROR: missing key or key_combination"
            resp = self.client.send_command("key_event", {"key": key, "modifiers": modifiers})
            return json.dumps(resp, ensure_ascii=False)

        if action == "type":
            text = str(kwargs.get("text", ""))
            resp = self.client.send_command("type_text", {"value": text})
            return json.dumps(resp, ensure_ascii=False)

        if action == "scroll":
            if "dx" in kwargs or "dy" in kwargs:
                dx = int(kwargs.get("dx", 0) or 0)
                dy = int(kwargs.get("dy", 0) or 0)
            else:
                direction = str(kwargs.get("direction", "down")).strip().lower()
                amount = int(kwargs.get("amount", 1) or 1)
                dx = 0
                dy = amount if direction == "down" else -amount
            resp = self.client.send_command("scroll", {"dx": dx, "dy": dy})
            return json.dumps(resp, ensure_ascii=False)

        return "ERROR: action must be click|double_click|right_click|move|hotkey|key|type|scroll|screenshot"
