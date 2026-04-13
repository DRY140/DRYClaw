from __future__ import annotations

from collections.abc import Callable
from typing import Any

from dryclaw.client.providers import LLMResponse, ProviderManager, ToolCall
from dryclaw.config.config import DryclawConfig


class LLMClient:
    # 此设计提供一个统一端口，不受各种厂商的SDK格式影响
    """统一 LLM 客户端入口。

    说明：
    1) 对外保持原有 `call_stream` / `check_auth` 接口不变。
    2) 具体 SDK 差异由 ProviderManager + Adapter 处理。
    3) 新增模型 API 时，不需要修改 AgentLoop，只需新增适配器并注册。
    """

    def __init__(
        self,
        config: DryclawConfig,
        adapter_factories: dict[str, Callable[[DryclawConfig], Any]] | None = None,
    ) -> None:

        self.config = config
        manager = ProviderManager(config=config, factories=adapter_factories)
        self.adapter = manager.create_adapter()

    def call_stream(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        system: str,
        on_text_delta: Callable[[str], None] | None = None,
        tool_choice: dict[str, Any] | None = None,
    ) -> LLMResponse:
        """流式调用统一出口，返回内部稳定响应结构。"""
        return self.adapter.call_stream(
            messages=messages, # 历史信息
            tools=tools, # 可用工具列表
            system=system,
            on_text_delta=on_text_delta,
            tool_choice=tool_choice, # 可选的工具选择参数，供某些模型使用
        )

    def check_auth(self) -> tuple[bool, str]:
        """轻量认证探测，用于 CLI --check-auth。"""
        return self.adapter.check_auth()


__all__ = ["LLMClient", "LLMResponse", "ToolCall", "ProviderManager"]
