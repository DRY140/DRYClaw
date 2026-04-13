from __future__ import annotations

import json
import re
import threading
from datetime import datetime
from pathlib import Path
from typing import Any


AUDIT_LOG = Path.home() / ".dryclaw" / "logs" / "audit.log"

_REDACT_PATTERNS = [
    re.compile(r"AKIA[A-Z0-9]{16}"),
    re.compile(r"eyJ[A-Za-z0-9+/=]{20,}\\.eyJ[A-Za-z0-9+/=]{10,}"),
    re.compile(r"sk-[A-Za-z0-9_-]{10,}"),
    re.compile(r"Bearer\\s+[A-Za-z0-9._-]{10,}", re.IGNORECASE),
    re.compile(r"-----BEGIN[\\s\\S]*?-----END[\\s\\S]*?-----"),
    re.compile(r"([A-Z_]{2,})=([^\\s]+)"),
    re.compile(r"sk-ant-[A-Za-z0-9_-]{10,}"),
]


class AuditLogger:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        AUDIT_LOG.parent.mkdir(parents=True, exist_ok=True)

    def log(
        self,
        *,
        tool_name: str,
        decision: str,
        args_preview: Any,
        result_preview: Any,
        duration_ms: int,
    ) -> None:
        payload = {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "tool_name": tool_name,
            "decision": decision,
            "args_preview": self._sanitize(str(args_preview))[:200],
            "result_preview": self._sanitize(str(result_preview))[:200],
            "duration_ms": max(0, int(duration_ms)),
        }

        line = json.dumps(payload, ensure_ascii=False)
        with self._lock:
            with AUDIT_LOG.open("a", encoding="utf-8") as f:
                f.write(line + "\n")

    @staticmethod
    def _sanitize(text: str) -> str:
        sanitized = text
        for pattern in _REDACT_PATTERNS:
            if pattern.pattern == r"([A-Z_]{2,})=([^\\s]+)":
                sanitized = pattern.sub(lambda m: f"{m.group(1)}=[REDACTED]", sanitized)
            else:
                sanitized = pattern.sub("[REDACTED]", sanitized)
        return sanitized


_audit_singleton: AuditLogger | None = None


def get_audit_logger() -> AuditLogger:
    global _audit_singleton
    if _audit_singleton is None:
        _audit_singleton = AuditLogger()
    return _audit_singleton
