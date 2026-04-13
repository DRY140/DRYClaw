from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from dryclaw.client.llm import LLMClient


@dataclass
class CompactResult:
    history: list[dict[str, Any]]
    compacted: bool
    reason: str = ""


class ContextWindowShaper:
    """ShanClaw ShapeHistory 风格的上下文窗口压缩器。"""

    compact_threshold: float = 0.85

    @staticmethod
    def estimate_tokens(history: list[dict[str, Any]]) -> int:
        total_chars = 0
        for msg in history:
            content = msg.get("content", "")
            total_chars += len(str(content))
        # 对齐 ShanClaw 的保守估算：chars/3.5 + 每条消息 4 token 开销。
        return int(total_chars / 3.5 + len(history) * 4)

    def should_compact(self, history: list[dict[str, Any]], context_window: int) -> bool:
        if context_window <= 0 or len(history) < 8:
            return False
        estimated = self.estimate_tokens(history)
        ratio = estimated / float(context_window)
        return ratio > self.compact_threshold

    def compact(self, history: list[dict[str, Any]], llm: LLMClient, context_window: int) -> CompactResult:
        if len(history) <= 4:
            return CompactResult(history=history, compacted=False, reason="history too short")

        if not self.should_compact(history, context_window):
            return CompactResult(history=history, compacted=False, reason="below threshold")

        first_user = None
        for item in history:
            if item.get("role") == "user":
                first_user = item
                break

        keep_last = 20
        minimum_keep = 3
        target_tokens = int(context_window * self.compact_threshold)
        chosen_history = list(history)

        while keep_last >= minimum_keep:
            recent = history[-keep_last:] if keep_last <= len(history) else list(history)
            candidate = []
            if first_user is not None and (not recent or first_user is not recent[0]):
                candidate.append(first_user)
            candidate.extend(recent)

            if self.estimate_tokens(candidate) <= target_tokens:
                chosen_history = candidate
                break
            keep_last -= 1

        truncate_count = max(len(history) - len(chosen_history), 0)
        truncated = history[:truncate_count]
        if not truncated:
            return CompactResult(history=chosen_history, compacted=False, reason="nothing truncated")

        summary_text = self._summarize(truncated, llm)
        summary_message = {
            "role": "assistant",
            "content": (
                "[历史摘要]\n"
                f"以下为被压缩上下文的摘要，请基于该摘要继续任务：\n{summary_text}"
            ),
        }

        compacted_history: list[dict[str, Any]] = []
        if first_user is not None:
            compacted_history.append(first_user)
        compacted_history.append(summary_message)

        for msg in chosen_history:
            if first_user is not None and msg is first_user:
                continue
            compacted_history.append(msg)

        return CompactResult(history=compacted_history, compacted=True, reason=f"keep_last={keep_last}")

    def _summarize(self, truncated: list[dict[str, Any]], llm: LLMClient) -> str:
        prompt = (
            "请将以下历史对话总结为要点，保留：任务目标、已尝试方法、失败原因、当前结论、待办。"
            "输出 8 条以内短句。\n\n"
            f"history={truncated}"
        )
        try:
            resp = llm.call_stream(
                messages=[{"role": "user", "content": prompt}],
                tools=[],
                system="你是一个负责压缩上下文的总结助手。",
                on_text_delta=None,
            )
            text = (resp.text or "").strip()
            return text or "（摘要生成失败，未获得文本）"
        except Exception as exc:
            return f"（摘要生成失败，已回退。错误: {exc}）"
