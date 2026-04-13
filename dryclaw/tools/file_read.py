from __future__ import annotations

from pathlib import Path


class FileReadTool:
    name = "file_read"
    description = "Read file with line numbers"
    input_schema = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Path to file"},
            "offset": {"type": "integer", "minimum": 1, "default": 1},
            "limit": {"type": "integer", "minimum": 1, "default": 2000},
        },
        "required": ["path"],
    }

    def run(self, **kwargs) -> str:
        path = str(kwargs.get("path", "")).strip()
        offset = int(kwargs.get("offset", 1) or 1)
        limit = int(kwargs.get("limit", 2000) or 2000)

        if not path:
            return "ERROR: missing path"

        target = Path(path).expanduser()
        if not target.exists():
            return f"ERROR: file not found: {target}"
        if target.is_dir():
            return f"ERROR: expected file but got directory: {target}"

        lines = target.read_text(encoding="utf-8", errors="replace").splitlines()
        start_idx = max(offset - 1, 0)
        end_idx = min(start_idx + limit, len(lines))

        output: list[str] = []
        for i in range(start_idx, end_idx):
            # 行号格式严格保持为右对齐数字 + tab，供后续 file_edit 复用。
            output.append(f"{i + 1:>4}\t{lines[i]}")

        if not output:
            return ""
        return "\n".join(output)
