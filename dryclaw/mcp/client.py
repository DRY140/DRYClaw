from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from dryclaw.tools.registry import ToolRegistry


@dataclass
class MCPServerConfig:
    name: str
    transport: str = "stdio"
    command: str = ""
    args: list[str] | None = None
    url: str = ""


class MCPClientManager:
    """Stage3 MCP 管理骨架：解析配置并保留刷新入口。"""

    def __init__(self) -> None:
        self._servers: list[MCPServerConfig] = []

    def load_from_config(self, raw: list[dict[str, Any]] | None) -> None:
        self._servers = []
        for item in raw or []:
            if not isinstance(item, dict):
                continue
            self._servers.append(
                MCPServerConfig(
                    name=str(item.get("name", "")).strip(),
                    transport=str(item.get("transport", "stdio")).strip().lower() or "stdio",
                    command=str(item.get("command", "")).strip(),
                    args=list(item.get("args") or []),
                    url=str(item.get("url", "")).strip(),
                )
            )

    def refresh_tools(self, registry: ToolRegistry) -> int:
        # 当前阶段先实现配置解析和安全空行为，避免无 MCP 环境时报错。
        # 后续接入真实 SDK 时，动态将远端 tools 注册到 registry。
        return 0

    @property
    def servers(self) -> list[MCPServerConfig]:
        return list(self._servers)
