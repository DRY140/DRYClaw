from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
import time
from typing import Any

from dryclaw.agent.context_window import ContextWindowShaper
from dryclaw.agent.loop_detect import Action, LoopDetector
from dryclaw.agent.read_tracker import ReadTracker
from dryclaw.audit.logger import get_audit_logger
from dryclaw.client.llm import LLMClient
from dryclaw.config.config import DryclawConfig
from dryclaw.output.renderer import Renderer
from dryclaw.permissions.engine import Decision, PermissionEngine
from dryclaw.prompt.builder import build_system_prompt
from dryclaw.tools.registry import ToolRegistry


@dataclass
class AgentLoop:
    config: DryclawConfig
    tools: ToolRegistry
    history: list[dict[str, Any]] = field(default_factory=list) #创建一个空列表，列表每一项是一个字典，字典的键是字符串，值可以是任意类型。这个 history 用于记录整个对话的历史，包括用户消息、助手回复、工具调用等。
    max_iterations: int = 25
    auto_approve: bool = False

    def __post_init__(self) -> None:
        self.max_iterations = self.config.max_iterations 
        self.renderer = Renderer() # 终端渲染
        self.llm = LLMClient(self.config) # LLM 调用客户端
        self.permission_engine = PermissionEngine() # 权限引擎
        self.read_tracker = ReadTracker() # 读前保护
        self.loop_detector = LoopDetector() # 循环检测
        self.context_window_shaper = ContextWindowShaper() # 上下文压缩
        self.audit_logger = get_audit_logger() # 审计日志

    def _ask_approval(self, tool_name: str, args: dict[str, Any]) -> bool:
        if self.auto_approve:
            return True
        c = self.renderer.console
        # 摘要行：突出工具名和关键参数
        key_arg = ""
        if "path" in args:
            key_arg = f" → {args['path']}"
        elif "command" in args:
            cmd = str(args["command"])
            key_arg = f" → {cmd[:60]}..." if len(cmd) > 60 else f" → {cmd}"
        elif "url" in args:
            key_arg = f" → {args['url']}"
        c.print(f"\n  [bold yellow]? {tool_name}[/bold yellow][dim]{key_arg}[/dim]")
        # 详细参数（跳过已在摘要中展示的 + 截断长值）
        for k, v in args.items():
            s = str(v).replace("\n", " ")
            if len(s) > 60:
                s = s[:60] + "..."
            c.print(f"    [dim]{k}:[/dim] {s}", highlight=False)
        # 琥珀色审批提示
        answer = input("\033[1;38;5;214m  允许执行？[y/N]\033[0m ").strip().lower()
        return answer in {"y", "yes"}

    def reset_for_new_turn(self) -> None:
        """多轮对话时，每轮开始前重置单轮状态（保留 history）。"""
        self.loop_detector = LoopDetector()
        self.read_tracker = ReadTracker()

    @staticmethod
    def _display_preview(tool_name: str, tool_input: dict[str, Any], result: str) -> str:
        """为终端生成简短摘要，避免刷屏。返回 None 则使用原始 result。"""
        if result.startswith("ERROR:"):
            return result

        computer_warning = AgentLoop._computer_target_warning(tool_name, result)
        if computer_warning:
            return computer_warning

        # 截图结果：只显示尺寸信息，不显示 base64
        action = str(tool_input.get("action", "")).strip().lower()
        is_screenshot = tool_name == "screenshot" or (tool_name == "computer" and action == "screenshot")
        if is_screenshot:
            try:
                data = json.loads(result)
                if isinstance(data, dict) and data.get("base64"):
                    saved = data.get("saved_to", "")
                    msg = f"screenshot captured ({data.get('width')}x{data.get('height')}, {data.get('format', 'jpeg')})"
                    if saved:
                        msg += f" -> {saved}"
                    return msg
            except Exception:
                pass

        # accessibility read_tree 结果：只显示元素计数
        if tool_name == "accessibility" and action == "read_tree":
            try:
                data = json.loads(result)
                if isinstance(data, dict) and data.get("ok"):
                    # 统计元素个数（通过计算 "ref" 出现次数）
                    ref_count = result.count('"ref"')
                    app = data.get("app", "")
                    msg = f"accessibility tree: {ref_count} elements"
                    if app:
                        msg = f"{app} — {msg}"
                    return msg
            except Exception:
                pass

        return result

    @staticmethod
    def _computer_target_warning(tool_name: str, result: str) -> str:
        if tool_name != "computer":
            return ""
        try:
            data = json.loads(result)
            if not isinstance(data, dict):
                return ""
            app = str(data.get("context", {}).get("app", "")).strip()
            if "终端" in app or "Terminal" in app:
                return f"⚠ 操作目标是「{app}」而非浏览器，请先用 focus 切换目标 app"
        except Exception:
            return ""
        return ""

    @staticmethod
    def _tool_result_content(tool_name: str, tool_input: dict[str, Any], result: str) -> Any:
        computer_warning = AgentLoop._computer_target_warning(tool_name, result)

        action = str(tool_input.get("action", "")).strip().lower()
        is_screenshot = tool_name == "screenshot" or (tool_name == "computer" and action == "screenshot")
        if not is_screenshot:
            if computer_warning and isinstance(result, str):
                return f"{computer_warning}\n{result}"
            return result

        if not isinstance(result, str) or result.startswith("ERROR:"):
            return result

        try:
            data = json.loads(result)
        except Exception:
            return result

        if not isinstance(data, dict):
            return result

        b64 = str(data.get("base64", "")).strip()
        image_format = str(data.get("format", "jpeg")).strip().lower()
        if not b64:
            if computer_warning:
                return f"{computer_warning}\n{result}"
            return result

        media_type = "image/png" if image_format == "png" else "image/jpeg"
        text_msg = f"screenshot captured ({data.get('width')}x{data.get('height')}, {image_format})"
        if computer_warning:
            text_msg = f"{computer_warning}\n{text_msg}"
        return [
            {
                "type": "text",
                "text": text_msg,
            },
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": media_type,
                    "data": b64,
                },
            },
        ]

    # 核心的run 方法，输入的是用户的提示词
    async def run(self, user_message: str) -> str:
        cwd = str(Path.cwd())
        system_prompt = build_system_prompt(cwd)
        self.history.append({"role": "user", "content": user_message})

        # 进入LOOP
        # 终止条件：达到最大轮次或模型直接给出最终回答（不再触发工具）。
        for iteration_count in range(self.max_iterations):
            if self.context_window_shaper.should_compact(self.history, self.config.context_window):
                compact_result = self.context_window_shaper.compact(
                    history=self.history,
                    llm=self.llm,
                    context_window=self.config.context_window,
                )
                if compact_result.compacted:
                    self.history = compact_result.history

            # 调用 LLM，传入历史消息、工具信息、系统提示等，获取 回复resp
            resp = self.llm.call_stream(
                # 传入所需的信息 
                messages=self.history,
                tools=self.tools.schemas(),
                system=system_prompt,
                # 增量渲染回调，实现终端的流式输出
                on_text_delta=self.renderer.print_text_delta,
            )
            self.renderer.print_newline()

            # LLM的返回里 没有工具调用 ：说明完成任务
            if not resp.tool_calls:
                self.history.append({"role": "assistant", "content": resp.text})
                return resp.text

            # LLM的返回里 有工具调用 ：先写入历史         
            assistant_blocks: list[dict[str, Any]] = []
            # 嵌套式地写入文本和工具调用，保持顺序和层级关系，供后续处理和渲染使用。
            if resp.text:
                assistant_blocks.append({"type": "text", "text": resp.text})
            for call in resp.tool_calls:
                assistant_blocks.append(
                    {
                        "type": "tool_use",
                        "id": call.id,
                        "name": call.name,
                        "input": call.input,
                    }
                )
            self.history.append({"role": "assistant", "content": assistant_blocks})

            # 然后调用工具
            tool_result_blocks: list[dict[str, Any]] = []
            force_stop = False
            # 遍历工具调用列表
            for call in resp.tool_calls:
                self.renderer.print_tool_call(call.name, call.input)
                tool = self.tools.get(call.name)
                decision = Decision.ASK
                started = time.perf_counter()
                if tool is None:
                    decision = Decision.DENY
                    result = f"ERROR: unknown tool: {call.name}"
                else:
                    try:
                        # 读前保护：如果是 file_edit 工具，且目标文件之前没有被 file_read 读取过，则拒绝执行，并返回错误提示。
                        if call.name == "file_edit":
                            target_path = str(call.input.get("path", ""))
                            if not self.read_tracker.is_read(target_path):
                                result = "ERROR: 请先用 file_read 读取该文件"
                            else:
                                result = ""
                        else:
                            result = ""

                        # 权限判定
                        if not result:
                            decision = self.permission_engine.decide_for_tool(call.name, call.input)
                            if decision == Decision.DENY:
                                result = f"ERROR: permission denied for tool {call.name}"
                            elif decision == Decision.ASK and not self._ask_approval(call.name, call.input):
                                result = f"ERROR: user denied tool {call.name}"
                            else:
                                result = tool.run(**call.input)

                        # 针对读取操作，读完进行标记，供后续的读前保护使用。
                        if call.name == "file_read" and not str(result).startswith("ERROR:"):
                            read_path = str(call.input.get("path", "")).strip()
                            if read_path:
                                self.read_tracker.mark_read(read_path)
                        
                        # 循环检测，利用loop_detector检测是否存在循环调用这种错误
                        signal = self.loop_detector.check(call.name, call.input, result)
                        if signal.action == Action.NUDGE:
                            # 将提醒嵌入工具结果中，LLM 更容易感知
                            result = f"{result}\n\n⚠️ 系统提醒：{signal.reason}，如果任务无法完成请直接告知用户。"
                        elif signal.action == Action.FORCE_STOP:
                            result = f"ERROR: {signal.reason}"
                            force_stop = True
                    except Exception as exc:
                        result = f"ERROR: tool {call.name} failed: {exc}"

                duration_ms = int((time.perf_counter() - started) * 1000)
                self.audit_logger.log(
                    tool_name=call.name,
                    decision=decision.value,
                    args_preview=call.input,
                    result_preview=result,
                    duration_ms=duration_ms,
                )

                self.renderer.print_tool_result_preview(
                    self._display_preview(call.name, call.input, result)
                )

                # 关键格式：tool_result 必须作为 role=user 回传，并精确匹配 tool_use_id。
                tool_result_blocks.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": call.id,
                        "content": self._tool_result_content(call.name, call.input, result),
                    }
                )

                # FORCE_STOP 时立即中断工具处理
                if force_stop:
                    break

            self.history.append({"role": "user", "content": tool_result_blocks})

            # FORCE_STOP：注入强制终止消息，让 LLM 只能输出最终回答
            if force_stop:
                self.history.append(
                    {
                        "role": "user",
                        "content": "⚠️ 系统强制终止：检测到无效循环。请直接回答用户，说明当前任务无法完成及原因。不要再调用任何工具。",
                    }
                )

            # 反思注入：第6轮时提醒 agent 回顾已有信息
            if iteration_count == 5:
                self.history.append(
                    {
                        "role": "user",
                        "content": "系统提醒：你已执行了6轮工具调用。请回顾已有信息，判断：1) 任务是否可行？2) 如果不可行，直接告知用户。3) 如果可行，描述接下来的明确计划。",
                    }
                )

        final_text = "Reached max iterations without final answer."
        self.history.append({"role": "assistant", "content": final_text})
        return final_text
