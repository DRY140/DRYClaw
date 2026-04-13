from __future__ import annotations

from pathlib import Path

MEMORY_FILE = Path.home() / ".dryclaw" / "MEMORY.md"


class MemoryAppendTool:
    name = "memory_append"
    description = "Append durable memory into ~/.dryclaw/MEMORY.md"
    input_schema = {
        "type": "object",
        "properties": {
            "content": {"type": "string", "description": "Text to append into MEMORY.md"},
        },
        "required": ["content"],
    }

    def run(self, **kwargs) -> str:
        import fcntl

        content = str(kwargs.get("content", "")).strip()
        if not content:
            return "ERROR: missing content"

        MEMORY_FILE.parent.mkdir(parents=True, exist_ok=True)
        with MEMORY_FILE.open("a+", encoding="utf-8") as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            f.write(content)
            f.write("\n")
            f.flush()
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)

        return f"OK: appended memory -> {MEMORY_FILE}"
