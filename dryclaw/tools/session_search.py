from __future__ import annotations

from dryclaw.session.store import SessionStore


class SessionSearchTool:
    name = "session_search"
    description = "Search previous sessions using SQLite FTS5 index"
    input_schema = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Full-text query"},
            "limit": {"type": "integer", "description": "Max rows", "default": 5},
        },
        "required": ["query"],
    }

    def run(self, **kwargs) -> str:
        query = str(kwargs.get("query", "")).strip()
        limit = int(kwargs.get("limit", 5) or 5)
        if not query:
            return "ERROR: missing query"

        rows = SessionStore().search(query=query, limit=max(1, min(20, limit)))
        if not rows:
            return "No matched sessions."

        lines = []
        for row in rows:
            lines.append(f"{row.id} | {row.created_at} | {row.snippet}")
        return "\n".join(lines)
