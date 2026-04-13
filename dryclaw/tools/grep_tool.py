from __future__ import annotations

import re
from pathlib import Path


class GrepTool:
    name = "grep"
    description = "Search text recursively" # 检索功能
    input_schema = {
        "type": "object",
        "properties": {
            "pattern": {"type": "string", "description": "Regex pattern"},
            "path": {"type": "string", "description": "Root directory", "default": "."},
        },
        "required": ["pattern"],
    }

    def run(self, **kwargs) -> str:
        pattern = str(kwargs.get("pattern", "")).strip()
        root = str(kwargs.get("path", ".")).strip() or "."

        if not pattern:
            return "ERROR: missing pattern"

        try:
            regex = re.compile(pattern)
        except re.error as exc:
            return f"ERROR: invalid regex: {exc}"

        root_path = Path(root).expanduser()
        if not root_path.exists():
            return f"ERROR: path not found: {root_path}"

        results: list[str] = []
        for file_path in root_path.rglob("*"):
            if len(results) >= 100:
                break
            if not file_path.is_file():
                continue
            try:
                for idx, line in enumerate(
                    file_path.read_text(encoding="utf-8", errors="replace").splitlines(),
                    start=1,
                ):
                    if regex.search(line):
                        results.append(f"{file_path}:{idx}:{line}")
                        if len(results) >= 100:
                            break
            except Exception:
                continue

        return "\n".join(results)
