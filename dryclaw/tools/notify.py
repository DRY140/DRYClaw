from __future__ import annotations

import subprocess


class NotifyTool:
    name = "notify"
    description = "Send a macOS desktop notification"
    input_schema = {
        "type": "object",
        "properties": {
            "message": {"type": "string", "description": "Notification text"},
            "title": {"type": "string", "description": "Notification title", "default": "dryclaw"},
        },
        "required": ["message"],
    }

    def run(self, **kwargs) -> str:
        message = str(kwargs.get("message", "")).strip()
        title = str(kwargs.get("title", "dryclaw")).strip() or "dryclaw"
        if not message:
            return "ERROR: missing message"

        safe_msg = message.replace('"', "'")
        safe_title = title.replace('"', "'")

        cmd = [
            "osascript",
            "-e",
            f'display notification "{safe_msg}" with title "{safe_title}"',
        ]
        try:
            subprocess.run(cmd, check=True, capture_output=True)
            return "OK: notification sent"
        except Exception as exc:
            return f"ERROR: notify failed: {exc}"
