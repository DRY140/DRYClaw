from __future__ import annotations

import json
from collections import Counter
from collections import deque
from dataclasses import dataclass
from enum import Enum


class Action(str, Enum):
    # 定义集中处理动作 - 正常继续、提醒改变策略、强制停止
    CONTINUE = "continue"
    NUDGE = "nudge"
    FORCE_STOP = "force_stop"


@dataclass
class LoopSignal:
    action: Action
    reason: str = ""


class LoopDetector:
    """Stage4 完整卡死检测（9种）。"""

    def __init__(self) -> None:
        self._last_signature: str | None = None
        self._consecutive_same = 0
        self._window: deque[str] = deque(maxlen=20)
        self._same_tool_error_name: str | None = None
        self._same_tool_error_count = 0

        self._no_progress_tool: str | None = None
        self._no_progress_count = 0

        # 跨工具连续空结果计数（不限同一工具）
        self._empty_result_streak = 0
        # NUDGE 后的 grace 期：期间内再触发 NUDGE 条件则升级为 FORCE_STOP
        self._nudge_grace = 0

        self._sleep_bash_count = 0

        self._last_mode_tool: str | None = None
        self._mode_switch_count = 0

        self._success_signatures: set[str] = set()
        self._success_then_error: Counter[str] = Counter()

        self._visual_family: deque[str] = deque(maxlen=6)

        self._last_search_score: int | None = None
        self._search_escalation_count = 0
        self._wrong_target_count = 0

        # 交替循环检测：追踪最近工具名序列
        self._recent_tools: deque[str] = deque(maxlen=6)

    @staticmethod
    def _computer_context_app(result: str) -> str:
        try:
            data = json.loads(result)
            if isinstance(data, dict):
                return str(data.get("context", {}).get("app", "")).strip()
        except Exception:
            return ""
        return ""

    @staticmethod
    def _signature(tool_name: str, args: dict) -> str:
        payload = json.dumps(args, ensure_ascii=False, sort_keys=True)
        return f"{tool_name}:{payload}"

    @staticmethod
    def _is_error(result: str) -> bool:
        return str(result).startswith("ERROR:")

    @staticmethod
    def _visual_state_key(tool_name: str, args: dict, result: str) -> str:
        _ = args
        return f"{tool_name}:{str(result)[:200]}"

    @staticmethod
    def _search_scope_score(tool_name: str, args: dict) -> int:
        if tool_name == "glob":
            pattern = str(args.get("pattern", ""))
            root = str(args.get("path", "."))
            return pattern.count("*") * 2 + pattern.count("**") * 4 + root.count("/")

        if tool_name == "grep":
            root = str(args.get("path", "."))
            pattern = str(args.get("pattern", ""))
            score = root.count("/") + len(pattern) // 8
            if root in {".", "./"}:
                score += 3
            return score

        return 0

    def _detect_cycle(self) -> int:
        """检测交替循环模式，返回重复次数（0表示无循环）。"""
        tools = list(self._recent_tools)
        n = len(tools)
        # 检测长度为2的循环：A,B,A,B...
        if n >= 4:
            pat = tools[-2:]
            repeats = 1
            i = n - 4
            while i >= 0 and tools[i : i + 2] == pat:
                repeats += 1
                i -= 2
            if repeats >= 2:
                return repeats
        # 检测长度为3的循环：A,B,C,A,B,C
        if n >= 6:
            pat = tools[-3:]
            if tools[-6:-3] == pat:
                return 2
        return 0

    def check(self, tool_name: str, args: dict, result: str) -> LoopSignal:
        sig = self._signature(tool_name, args)
        self._window.append(sig)
        self._recent_tools.append(tool_name)

        if self._last_signature == sig:
            self._consecutive_same += 1
        else:
            self._consecutive_same = 1
        self._last_signature = sig

        repeats_in_window = sum(1 for item in self._window if item == sig)

        is_error = self._is_error(result)
        is_empty = not str(result).strip()

        # 跨工具连续空结果计数
        if is_empty:
            self._empty_result_streak += 1
        else:
            self._empty_result_streak = 0
        if is_error and self._same_tool_error_name == tool_name:
            self._same_tool_error_count += 1
        elif is_error:
            self._same_tool_error_name = tool_name
            self._same_tool_error_count = 1
        else:
            self._same_tool_error_name = None
            self._same_tool_error_count = 0

        # 4) NoProgress: 同一工具无进展反复调用。
        no_progress = is_error or not str(result).strip()
        if no_progress and self._no_progress_tool == tool_name:
            self._no_progress_count += 1
        elif no_progress:
            self._no_progress_tool = tool_name
            self._no_progress_count = 1
        else:
            self._no_progress_tool = None
            self._no_progress_count = 0

        # 5) Sleep: bash 里反复出现 sleep。
        command = str(args.get("command", ""))
        if tool_name == "bash" and "sleep" in command:
            self._sleep_bash_count += 1
        else:
            self._sleep_bash_count = 0

        # 6) ToolModeSwitch: accessibility/computer 模式反复切换。
        if tool_name in {"accessibility", "computer"}:
            if self._last_mode_tool and self._last_mode_tool != tool_name:
                self._mode_switch_count += 1
            self._last_mode_tool = tool_name

        # 7) SuccessAfterError: 成功后又连续报错。
        if not is_error:
            self._success_signatures.add(sig)
            self._success_then_error[sig] = 0
        elif sig in self._success_signatures:
            self._success_then_error[sig] += 1

        # 8) FamilyNoProgress: screenshot/accessibility 连续调用且状态不变。
        if tool_name in {"screenshot", "accessibility"}:
            self._visual_family.append(self._visual_state_key(tool_name, args, result))
        else:
            self._visual_family.clear()

        # 9) SearchEscalation: glob/grep 搜索范围持续扩大。
        if tool_name in {"glob", "grep"}:
            score = self._search_scope_score(tool_name, args)
            if self._last_search_score is not None and score > self._last_search_score:
                self._search_escalation_count += 1
            elif self._last_search_score is not None and score < self._last_search_score:
                self._search_escalation_count = max(0, self._search_escalation_count - 1)
            self._last_search_score = score

        # 10) WrongTargetApp: computer 操作连续作用在终端而非目标应用。
        if tool_name == "computer":
            app = self._computer_context_app(result)
            if app and ("终端" in app or "Terminal" in app):
                self._wrong_target_count += 1
            else:
                self._wrong_target_count = 0
        else:
            self._wrong_target_count = 0

        # --- 判定区域 ---

        # 交替循环检测（A→B→A→B 模式）
        cycle_repeats = self._detect_cycle()

        # FORCE_STOP 级别
        if self._no_progress_count >= 8:
            return LoopSignal(Action.FORCE_STOP, "同一工具无进展调用过多，强制停止")

        if self._empty_result_streak >= 8:
            return LoopSignal(Action.FORCE_STOP, "连续多次调用均无结果，强制停止")

        if self._consecutive_same >= 3 or repeats_in_window >= 5 or self._same_tool_error_count >= 8:
            return LoopSignal(Action.FORCE_STOP, "检测到可能死循环，强制停止")

        if cycle_repeats >= 3:
            return LoopSignal(Action.FORCE_STOP, "检测到交替循环模式，强制停止")

        # NUDGE 级别（grace 期间内升级为 FORCE_STOP）
        def _emit_nudge(reason: str) -> LoopSignal:
            if self._nudge_grace > 0:
                # grace 期间内再次触发 NUDGE 条件 → 升级为 FORCE_STOP
                self._nudge_grace = 0
                return LoopSignal(Action.FORCE_STOP, f"{reason}（提醒后仍未改善，强制停止）")
            self._nudge_grace = 2  # 未来2次调用内再触发则升级
            return LoopSignal(Action.NUDGE, reason)

        # 递减 grace 计数器（放在 _emit_nudge 定义后、所有 NUDGE 检查前）
        if self._nudge_grace > 0:
            self._nudge_grace -= 1

        if cycle_repeats >= 2:
            return _emit_nudge("检测到交替循环模式，请改变策略或告知用户任务无法完成")

        if self._empty_result_streak >= 5:
            return _emit_nudge("连续多次调用均无结果，请考虑任务是否可行并告知用户")

        if self._no_progress_count >= 4:
            return _emit_nudge("同一工具无进展调用过多，请更换策略")

        if self._sleep_bash_count >= 2:
            return _emit_nudge("检测到 sleep 轮询，请改用 wait_for 或事件机制")

        if self._mode_switch_count > 4:
            return _emit_nudge("accessibility 与 computer 模式反复切换，请收敛策略")

        if self._success_then_error[sig] > 3:
            return _emit_nudge("同一操作成功后反复报错，请检查上下文状态")

        if len(self._visual_family) == 6 and len(set(self._visual_family)) == 1:
            return _emit_nudge("视觉类工具连续无变化，请避免重复截图/读取")

        if self._search_escalation_count > 5:
            return _emit_nudge("检测到搜索范围持续升级，请先缩小问题空间")

        if self._wrong_target_count >= 2:
            return _emit_nudge("computer 连续操作在终端上，请先 focus 到目标应用后再操作")

        if self._consecutive_same >= 2 or repeats_in_window >= 3 or self._same_tool_error_count >= 4:
            return _emit_nudge("检测到重复调用趋势，请改变策略")

        return LoopSignal(Action.CONTINUE, "")
