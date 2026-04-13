from __future__ import annotations

import os
from pathlib import Path


class FileEditTool:
    name = "file_edit"
    description = "Edit file by unique old_string replacement"
    input_schema = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Target file path"},
            "old_string": {"type": "string", "description": "String to replace (must be unique)"},
            "new_string": {"type": "string", "description": "Replacement string"},
        },
        "required": ["path", "old_string", "new_string"],
    }

    def run(self, **kwargs) -> str:
        path = str(kwargs.get("path", "")).strip()
        old_string = str(kwargs.get("old_string", ""))
        new_string = str(kwargs.get("new_string", ""))

        if not path:
            return "ERROR: missing path"
        if not old_string:
            return "ERROR: old_string is empty"

        target = Path(path).expanduser()
        if not target.exists():
            return f"ERROR: file not found: {target}"
        if target.is_dir():
            return f"ERROR: expected file but got directory: {target}"

        text = target.read_text(encoding="utf-8", errors="replace")
        count = text.count(old_string)
        # 唯一匹配约束：避免 LLM 模糊替换到错误位置。
        if count == 0:
            return "ERROR: old_string not found"
        if count > 1:
            return "ERROR: old_string is not unique"

        original_mode = target.stat().st_mode
        updated = text.replace(old_string, new_string, 1)
        target.write_text(updated, encoding="utf-8")
        os.chmod(target, original_mode)

        return f"OK: edited {target}"
