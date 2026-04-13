from __future__ import annotations

import subprocess
from pathlib import Path


class BashTool:
    name = "bash"
    description = "Execute shell command once"
    input_schema = {
        "type": "object",
        "properties": {
            "command": {"type": "string", "description": "Shell command"},
        },
        "required": ["command"],
    }

    def __init__(self, cwd: str | None = None) -> None:
        self.cwd = cwd or str(Path.cwd())

    def run(self, **kwargs) -> str:
        command = str(kwargs.get("command", "")).strip()
        if not command:
            return "ERROR: missing command"

        try:
            proc = subprocess.run(
                command,
                shell=True,
                cwd=self.cwd,
                text=True,
                capture_output=True,
                timeout=120,
            )
        except subprocess.TimeoutExpired:
            return "ERROR: command timed out after 120 seconds"
        except Exception as exc:
            return f"ERROR: bash failed: {exc}"

        combined = (proc.stdout or "") + (proc.stderr or "")
        if len(combined) > 30000:
            return combined[:30000] + "\n... [truncated to 30KB]"
        return combined
