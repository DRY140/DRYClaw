from __future__ import annotations

import os
from pathlib import Path


class FileWriteTool:
    name = "file_write"
    description = "Write full content to file"
    input_schema = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Target file path"},
            "content": {"type": "string", "description": "File content to write"},
        },
        "required": ["path", "content"],
    }

    def run(self, **kwargs) -> str:
        path = str(kwargs.get("path", "")).strip()
        content = str(kwargs.get("content", ""))
        if not path:
            return "ERROR: missing path"

        target = Path(path).expanduser()
        target.parent.mkdir(parents=True, exist_ok=True)

        original_mode: int | None = None
        if target.exists():
            original_mode = target.stat().st_mode

        target.write_text(content, encoding="utf-8")

        if original_mode is not None:
            os.chmod(target, original_mode)

        return f"OK: wrote {len(content)} chars to {target}"
