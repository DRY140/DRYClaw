from __future__ import annotations

import glob
from pathlib import Path


class GlobTool:
    name = "glob"
    description = "Search files by glob pattern"
    input_schema = {
        "type": "object",
        "properties": {
            "pattern": {"type": "string", "description": "Glob pattern, e.g. **/*.py"},
            "path": {"type": "string", "description": "Root directory", "default": "."},
        },
        "required": ["pattern"],
    }

    def run(self, **kwargs) -> str:
        pattern = str(kwargs.get("pattern", "")).strip()
        root = str(kwargs.get("path", ".")).strip() or "."

        if not pattern:
            return "ERROR: missing pattern"

        root_path = Path(root).expanduser()
        full_pattern = str(root_path / pattern)
        paths = [Path(p) for p in glob.glob(full_pattern, recursive=True)]
        files = [p for p in paths if p.exists()]

        # 与 ShanClaw 一致：按修改时间降序，便于优先看到最新文件。
        files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        return "\n".join(str(p) for p in files)
