from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol

from anthropic import Anthropic
from openai import OpenAI
from zai import ZhipuAiClient

from dryclaw.config.config import DryclawConfig


@dataclass
# 每个 toolcall 包含 三个东西 
# 1. id 标识符，方便关联用户消息中的 tool_result  
# 2. name 工具名，方便适配不同SDK的工具调用格式 
# 3. input 工具输入参数，字典格式
class ToolCall:
    id: str
    name: str
    input: dict[str, Any]


@dataclass
# 统一描述LLM的输出 包含两部分
# 1. text 模型生成的文本回复
# 2. tool_calls 模型触发的工具调用列表
class LLMResponse:
    text: str
    tool_calls: list[ToolCall]


def _as_dict(obj: Any) -> dict[str, Any]:
    """最大兼容地将 SDK 对象转换为 dict。"""
    # 格式上统一了不同 SDK 的 回复
    if isinstance(obj, dict):
        return obj
    if hasattr(obj, "model_dump"):
        try:
            data = obj.model_dump()
            if isinstance(data, dict):
                return data
        except Exception:
            pass
    result: dict[str, Any] = {}
    for key in dir(obj):
        if key.startswith("_"):
            continue
        try:
            value = getattr(obj, key)
        except Exception:
            continue
        if callable(value):
            continue
        result[key] = value
    return result


def _tool_content_to_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if not isinstance(block, dict):
                continue
            btype = str(block.get("type", ""))
            if btype == "text":
                parts.append(str(block.get("text", "")))
        return "\n".join(p for p in parts if p)
    return str(content)


def _tool_content_to_image_parts(content: Any) -> list[dict[str, Any]]:
    """从 tool_result.content 中提取可发送给多模态模型的图片块。

    返回 OpenAI 兼容 content parts：
    - {"type": "text", "text": ...}
    - {"type": "image_url", "image_url": {"url": "data:..."}}
    """
    if not isinstance(content, list):
        return []

    parts: list[dict[str, Any]] = []
    for block in content:
        if not isinstance(block, dict):
            continue
        btype = str(block.get("type", ""))
        if btype == "text":
            txt = str(block.get("text", "")).strip()
            if txt:
                parts.append({"type": "text", "text": txt})
            continue
        if btype != "image":
            continue

        source = block.get("source")
        if not isinstance(source, dict):
            continue
        if str(source.get("type", "")) != "base64":
            continue
        media_type = str(source.get("media_type", "image/jpeg") or "image/jpeg")
        data = str(source.get("data", "") or "").strip()
        if not data:
            continue
        parts.append(
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:{media_type};base64,{data}",
                },
            }
        )

    return parts


class ProviderAdapter(Protocol):
    """统一 provider 适配协议，新模型接入时仅实现本协议。"""
    # 没有具体的实现，只是一种规范，规定了所有的适配器都应该有这两个函数
    def call_stream(
        self,
        *,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        system: str,
        on_text_delta: Callable[[str], None] | None,
        tool_choice: dict[str, Any] | None,
    ) -> LLMResponse:
        ...

    def check_auth(self) -> tuple[bool, str]:
        ...


class AnthropicAdapter:
    """历史通道适配层：维持原有 Anthropic API 调用行为。"""

    def __init__(self, config: DryclawConfig) -> None:
        # 对于api调用 需要 key 和 base_url（可选）
        self.config = config
        self.client = Anthropic(api_key=config.api_key, base_url=config.api_base or None)

    def call_stream(
        self,
        *,
        messages: list[dict[str, Any]], # 历史对话
        tools: list[dict[str, Any]], # 工具列表
        system: str,
        on_text_delta: Callable[[str], None] | None,
        tool_choice: dict[str, Any] | None, # 预留项，暂时用不到，用来传输选定的工具及参数，
    ) -> LLMResponse: # 必须输出LLMResponse对象，包含文本和工具调用列表，前文定义过

        # 组装请求参数，如果是GLM或者其他，可能在这一步有转化步骤
        request_kwargs: dict[str, Any] = {
            "model": self.config.model,
            "max_tokens": 2048,
            "system": system,
            "messages": messages,
            "tools": tools,
        }
        if tool_choice:
            request_kwargs["tool_choice"] = tool_choice

        # 核心代码：发起流式请求与接收文本
        with self.client.messages.stream(**request_kwargs) as stream:
            chunks: list[str] = []
            # 如果有新的文本蹦回来了，就加入到chunks里
            # 如果开启了 on_text_delta 就同步打出在cli里
            for text in stream.text_stream: # 这里的text就是一小段文字
                chunks.append(text)
                if on_text_delta is not None:
                    on_text_delta(text)
            # 直接获取结构化回复，包含文本和工具调用列表，这相当于重复获取了一遍文本，但可以保证拿到完整的工具调用信息
            final_message = stream.get_final_message()
            
        # 解析与统一格式化输出
        text = "".join(chunks) # 这里得到纯文本，下面构建工具调用列表。
        tool_calls: list[ToolCall] = []
        # content 是一个列表，里面有纯文本，也有工具调用
        for block in final_message.content:
            # 抓取是工具调用的content
            if getattr(block, "type", "") != "tool_use":
                continue
            raw_input = getattr(block, "input", {}) or {}
            if not isinstance(raw_input, dict):
                try:
                    raw_input = json.loads(raw_input)
                except Exception:
                    raw_input = {}
            # 将工具调用的content，构造成标准的 ToolCall 对象
            tool_calls.append(
                ToolCall(
                    id=getattr(block, "id", ""),
                    name=getattr(block, "name", ""),
                    input=raw_input,
                )
            )

        return LLMResponse(text=text, tool_calls=tool_calls)

    def check_auth(self) -> tuple[bool, str]:
        try:
            self.client.messages.create(
                model=self.config.model,
                max_tokens=16,
                messages=[{"role": "user", "content": "ping"}],
            )
            return True, "ok"
        except Exception as exc:
            return False, str(exc)

# 【双向翻译层】：将系统原生的 Claude 格式（积木块、User身份返回），
# 与 OpenAI/GLM 规范（Function套壳、独立Tool角色、流式碎片拼接）进行互相转换适配。
class GLMAdapter:
    """GLM 官方 SDK 适配层，统一输出内部 LLMResponse。"""

    def __init__(self, config: DryclawConfig) -> None:
        self.config = config
        kwargs: dict[str, Any] = {"api_key": config.api_key}
        if config.api_base:
            kwargs["base_url"] = config.api_base
        self.client = ZhipuAiClient(**kwargs)

    @staticmethod
    def _convert_tools(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """将历史 Anthropic 工具 schema 转成 GLM 函数调用 schema。"""
        glm_tools: list[dict[str, Any]] = []
        for tool in tools:
            if tool.get("type") == "function" and isinstance(tool.get("function"), dict):
                glm_tools.append(tool)
                continue
            glm_tools.append(
                {
                    "type": "function",
                    "function": {
                        "name": tool.get("name", ""),
                        "description": tool.get("description", ""),
                        "parameters": tool.get("input_schema", {"type": "object", "properties": {}}),
                    },
                }
            )
        return glm_tools

    @staticmethod
    def _convert_tool_choice(tool_choice: dict[str, Any] | None) -> Any:
        if not tool_choice:
            return "auto"
        if tool_choice.get("type") == "tool" and tool_choice.get("name"):
            return {"type": "function", "function": {"name": str(tool_choice["name"])}}
        return "auto"

    @staticmethod
    def _convert_messages(messages: list[dict[str, Any]], system: str) -> list[dict[str, Any]]:
        """将 Stage 1 历史消息转换为 GLM chat.completions 格式。

        关键点：
        1) assistant/tool_use -> assistant.tool_calls
        2) user/tool_result -> role=tool + tool_call_id
        """

        out: list[dict[str, Any]] = []
        if system:
            out.append({"role": "system", "content": system})

        for msg in messages:
            role = str(msg.get("role", ""))
            content = msg.get("content")

            if isinstance(content, str):
                if role in {"user", "assistant"}:
                    out.append({"role": role, "content": content})
                continue

            if not isinstance(content, list):
                continue

            if role == "assistant":
                text_parts: list[str] = []
                tool_calls: list[dict[str, Any]] = []
                for block in content:
                    if not isinstance(block, dict):
                        continue
                    btype = block.get("type")
                    if btype == "text":
                        text_parts.append(str(block.get("text", "")))
                    elif btype == "tool_use":
                        tool_calls.append(
                            {
                                "id": str(block.get("id", "")),
                                "type": "function",
                                "function": {
                                    "name": str(block.get("name", "")),
                                    "arguments": json.dumps(block.get("input", {}), ensure_ascii=False),
                                },
                            }
                        )

                if text_parts or tool_calls:
                    out.append(
                        {
                            "role": "assistant",
                            "content": "\n".join(part for part in text_parts if part),
                            **({"tool_calls": tool_calls} if tool_calls else {}),
                        }
                    )
                continue

            if role == "user":
                for block in content:
                    if not isinstance(block, dict) or block.get("type") != "tool_result":
                        continue
                    raw_tool_content = block.get("content", "")
                    out.append(
                        {
                            "role": "tool",
                            "tool_call_id": str(block.get("tool_use_id", "")),
                            "content": _tool_content_to_text(raw_tool_content),
                        }
                    )

                    image_parts = _tool_content_to_image_parts(raw_tool_content)
                    if image_parts:
                        # 对 OpenAI 兼容多模态接口补充一条 user 消息，确保图片真实进入模型输入。
                        out.append({"role": "user", "content": image_parts})

        return out

    def call_stream(
        self,
        *,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        system: str,
        on_text_delta: Callable[[str], None] | None,
        tool_choice: dict[str, Any] | None,
    ) -> LLMResponse:
        glm_messages = self._convert_messages(messages, system)
        glm_tools = self._convert_tools(tools)
        glm_tool_choice = self._convert_tool_choice(tool_choice)

        stream = self.client.chat.completions.create(
            model=self.config.model,
            messages=glm_messages,
            tools=glm_tools,
            tool_choice=glm_tool_choice,
            stream=True,
            max_tokens=2048,
        )

        text_chunks: list[str] = []
        tool_chunks: dict[int, dict[str, Any]] = {}
        for chunk in stream:
            cdict = _as_dict(chunk)
            choices = cdict.get("choices") or []
            if not choices:
                continue
            delta = choices[0].get("delta") or {}

            text = delta.get("content")
            if isinstance(text, str) and text:
                text_chunks.append(text)
                if on_text_delta is not None:
                    on_text_delta(text)

            for tc in delta.get("tool_calls") or []:
                idx = int(tc.get("index", 0) or 0)
                slot = tool_chunks.setdefault(idx, {"id": "", "name": "", "args": []})
                if tc.get("id"):
                    slot["id"] = str(tc["id"])
                fn = tc.get("function") or {}
                if fn.get("name"):
                    slot["name"] = str(fn["name"])
                args_part = fn.get("arguments")
                if isinstance(args_part, str) and args_part:
                    slot["args"].append(args_part)

        tool_calls: list[ToolCall] = []
        for idx in sorted(tool_chunks.keys()):
            slot = tool_chunks[idx]
            arg_str = "".join(slot.get("args", []))
            parsed_input: dict[str, Any] = {}
            if arg_str:
                try:
                    loaded = json.loads(arg_str)
                    if isinstance(loaded, dict):
                        parsed_input = loaded
                except Exception:
                    parsed_input = {}

            tool_calls.append(
                ToolCall(
                    id=str(slot.get("id") or f"glm_tool_{idx}"),
                    name=str(slot.get("name") or ""),
                    input=parsed_input,
                )
            )

        return LLMResponse(text="".join(text_chunks), tool_calls=tool_calls)

    def check_auth(self) -> tuple[bool, str]:
        try:
            self.client.chat.completions.create(
                model=self.config.model,
                messages=[{"role": "user", "content": "ping"}],
                max_tokens=16,
            )
            return True, "ok"
        except Exception as exc:
            return False, str(exc)

# 【双向翻译层】：将系统原生的 Claude 格式（积木块、User身份返回），
# 与 OpenAI/GLM 规范（Function套壳、独立Tool角色、流式碎片拼接）进行互相转换适配。

class OpenAICompatAdapter:
    """OpenAI 兼容适配层（OpenAI/Ollama/Deepseek 等兼容接口）。"""

    def __init__(self, config: DryclawConfig) -> None:
        self.config = config
        kwargs: dict[str, Any] = {"api_key": config.api_key}
        if config.api_base:
            kwargs["base_url"] = config.api_base
        self.client = OpenAI(**kwargs)

    @staticmethod
    def _convert_tools(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
        converted: list[dict[str, Any]] = []
        for tool in tools:
            if tool.get("type") == "function" and isinstance(tool.get("function"), dict):
                converted.append(tool)
                continue
            converted.append(
                {
                    "type": "function",
                    "function": {
                        "name": tool.get("name", ""),
                        "description": tool.get("description", ""),
                        "parameters": tool.get("input_schema", {"type": "object", "properties": {}}),
                    },
                }
            )
        return converted

    @staticmethod
    def _convert_messages(messages: list[dict[str, Any]], system: str) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        if system:
            out.append({"role": "system", "content": system})

        for msg in messages:
            role = str(msg.get("role", ""))
            content = msg.get("content")

            if isinstance(content, str):
                if role in {"user", "assistant"}:
                    out.append({"role": role, "content": content})
                continue

            if not isinstance(content, list):
                continue

            if role == "assistant":
                text_parts: list[str] = []
                tool_calls: list[dict[str, Any]] = []
                for block in content:
                    if not isinstance(block, dict):
                        continue
                    if block.get("type") == "text":
                        text_parts.append(str(block.get("text", "")))
                    elif block.get("type") == "tool_use":
                        tool_calls.append(
                            {
                                "id": str(block.get("id", "")),
                                "type": "function",
                                "function": {
                                    "name": str(block.get("name", "")),
                                    "arguments": json.dumps(block.get("input", {}), ensure_ascii=False),
                                },
                            }
                        )
                out.append(
                    {
                        "role": "assistant",
                        "content": "\n".join(p for p in text_parts if p),
                        **({"tool_calls": tool_calls} if tool_calls else {}),
                    }
                )
                continue

            if role == "user":
                for block in content:
                    if not isinstance(block, dict) or block.get("type") != "tool_result":
                        continue
                    raw_tool_content = block.get("content", "")
                    out.append(
                        {
                            "role": "tool",
                            "tool_call_id": str(block.get("tool_use_id", "")),
                            "content": _tool_content_to_text(raw_tool_content),
                        }
                    )
                    image_parts = _tool_content_to_image_parts(raw_tool_content)
                    if image_parts:
                        out.append({"role": "user", "content": image_parts})
        return out

    def call_stream(
        self,
        *,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        system: str,
        on_text_delta: Callable[[str], None] | None,
        tool_choice: dict[str, Any] | None,
    ) -> LLMResponse:
        oai_messages = self._convert_messages(messages, system)
        oai_tools = self._convert_tools(tools)

        stream = self.client.chat.completions.create(
            model=self.config.model,
            messages=oai_messages,
            tools=oai_tools,
            tool_choice=(
                {"type": "function", "function": {"name": tool_choice.get("name")}}
                if tool_choice and tool_choice.get("type") == "tool" and tool_choice.get("name")
                else "auto"
            ),
            stream=True,
            max_tokens=2048,
        )

        text_chunks: list[str] = []
        tool_chunks: dict[int, dict[str, Any]] = {}

        for chunk in stream:
            cdict = _as_dict(chunk)
            choices = cdict.get("choices") or []
            if not choices:
                continue
            delta = choices[0].get("delta") or {}

            text = delta.get("content")
            if isinstance(text, str) and text:
                text_chunks.append(text)
                if on_text_delta is not None:
                    on_text_delta(text)

            for tc in delta.get("tool_calls") or []:
                idx = int(tc.get("index", 0) or 0)
                slot = tool_chunks.setdefault(idx, {"id": "", "name": "", "args": []})
                if tc.get("id"):
                    slot["id"] = str(tc["id"])
                fn = tc.get("function") or {}
                if fn.get("name"):
                    slot["name"] = str(fn["name"])
                arg_part = fn.get("arguments")
                if isinstance(arg_part, str) and arg_part:
                    slot["args"].append(arg_part)

        tool_calls: list[ToolCall] = []
        for idx in sorted(tool_chunks.keys()):
            slot = tool_chunks[idx]
            arg_str = "".join(slot.get("args", []))
            parsed: dict[str, Any] = {}
            if arg_str:
                try:
                    loaded = json.loads(arg_str)
                    if isinstance(loaded, dict):
                        parsed = loaded
                except Exception:
                    parsed = {}

            tool_calls.append(
                ToolCall(
                    id=str(slot.get("id") or f"openai_tool_{idx}"),
                    name=str(slot.get("name") or ""),
                    input=parsed,
                )
            )

        return LLMResponse(text="".join(text_chunks), tool_calls=tool_calls)

    def check_auth(self) -> tuple[bool, str]:
        try:
            self.client.chat.completions.create(
                model=self.config.model,
                messages=[{"role": "user", "content": "ping"}],
                max_tokens=16,
            )
            return True, "ok"
        except Exception as exc:
            return False, str(exc)


AdapterFactory = Callable[[DryclawConfig], ProviderAdapter]


class ProviderManager:
    """统一 Provider 管理器。

    设计目标：
    1) 保留老通道（anthropic）和新通道（glm）并存。
    2) 新增 provider 时仅需新增适配器类并注册 factory。
    3) 上层 LLMClient 与 AgentLoop 不感知具体 SDK。
    """
   
    # 默认的 provider 工厂，兼容三个
    _default_factories: dict[str, AdapterFactory] = {
        "anthropic": AnthropicAdapter,
        "glm": GLMAdapter,
        "openai": OpenAICompatAdapter,
    }

    def __init__(
        self,
        config: DryclawConfig,
        factories: dict[str, AdapterFactory] | None = None,
    ) -> None:
        self.config = config
        self.provider = (config.provider or "anthropic").strip().lower()
        self.factories = dict(self._default_factories)
        if factories:
            self.factories.update({k.strip().lower(): v for k, v in factories.items()})

    @classmethod
    def register_default_provider(cls, name: str, factory: AdapterFactory) -> None:
        """注册全局默认 provider 工厂，供后续扩展模型使用。"""
        cls._default_factories[name.strip().lower()] = factory

    # 依照provider工厂去创建，不存在的provider会抛出异常，正常的话返回一个provider实例
    def create_adapter(self) -> ProviderAdapter:
        factory = self.factories.get(self.provider)
        if factory is None:
            supported = ", ".join(sorted(self.factories.keys()))
            raise ValueError(f"Unsupported provider: {self.provider}. Supported providers: {supported}")
        return factory(self.config)
