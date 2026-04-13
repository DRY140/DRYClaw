from __future__ import annotations

import subprocess


class ClipboardTool:
    name = "clipboard"
    description = "Read or write macOS clipboard"
    input_schema = {
        "type": "object",
        "properties": {
            "action": {"type": "string", "description": "read or write", "default": "read"},
            "text": {"type": "string", "description": "Text for write", "default": ""},
        },
        "required": ["action"],
    }

    def run(self, **kwargs) -> str:
        action = str(kwargs.get("action", "read")).strip().lower()
        text = str(kwargs.get("text", ""))

        try:
            if action == "write":
                subprocess.run(["pbcopy"], input=text.encode("utf-8"), check=True)
                return "OK: clipboard updated"
            if action == "read":
                proc = subprocess.run(["pbpaste"], check=True, capture_output=True)
                return proc.stdout.decode("utf-8", errors="replace")
            return "ERROR: action must be read or write"
        except Exception as exc:
            return f"ERROR: clipboard failed: {exc}"
