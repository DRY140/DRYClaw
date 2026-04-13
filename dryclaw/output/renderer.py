from __future__ import annotations

from rich.console import Console
from rich.style import Style
from rich.text import Text


# 定义统一的终端渲染器
class Renderer:
    def __init__(self) -> None:
        self.console = Console()
        self.tool_style = Style(color="bright_black")

    def print_welcome(
        self,
        version: str = "0.1.0",
        provider: str = "",
        model: str = "",
        cwd: str = "",
    ) -> None:
        """渲染欢迎界面：方案B 深夜蓝调配色。"""
        w = 75
        bs = "color(69)"      # 边框：偏紫蓝
        cloud = "bold white"   # 云朵：亮白
        rain = "color(75)"     # 雨滴：亮天蓝
        tag = "color(75) italic"  # tagline
        name_style = "color(75) bold"  # DRYClaw 字样
        info_style = "color(245)"      # 信息行

        t = Text()
        t.append("╭" + "─" * w + "╮\n", style=bs)
        t.append("│" + " " * w + "│\n", style=bs)

        # 云朵
        for cl in ["▄▄████▄▄", "▄██████████▄", "▀▀▀▀▀▀▀▀▀▀▀▀"]:
            t.append("│", style=bs)
            t.append(cl.center(w), style=cloud)
            t.append("│\n", style=bs)

        # 雨滴
        t.append("│", style=bs)
        t.append("▞   ▞   ▞".center(w), style=rain)
        t.append("│\n", style=bs)

        t.append("│" + " " * w + "│\n", style=bs)

        # tagline
        t.append("│", style=bs)
        t.append('"Dry code, Lucky rain."'.center(w), style=tag)
        t.append("│\n", style=bs)

        t.append("│" + " " * w + "│\n", style=bs)

        # 信息行1：DRYClaw 蓝色 + 版本 + 右侧模式
        left1_name = "  DRYClaw"
        left1_ver = f" v{version}"
        right1 = "Mode: Autonomous Agent  "
        gap1 = w - len(left1_name) - len(left1_ver) - len(right1)
        t.append("│", style=bs)
        t.append(left1_name, style=name_style)
        t.append(left1_ver + " " * max(gap1, 1) + right1, style="white")
        t.append("│\n", style=bs)

        # 信息行2：Provider
        if provider:
            left2 = f"  Provider: {provider}/{model}"
        else:
            left2 = "  Environment: macOS"
        t.append("│", style=bs)
        t.append(left2.ljust(w), style=info_style)
        t.append("│\n", style=bs)

        # CWD 行
        if cwd:
            cwd_text = f"  CWD: {cwd}"
            if len(cwd_text) > w - 2:
                cwd_text = cwd_text[: w - 5] + "..."
            t.append("│", style=bs)
            t.append(cwd_text.ljust(w), style=info_style)
            t.append("│\n", style=bs)

        t.append("│" + " " * w + "│\n", style=bs)
        t.append("╰" + "─" * w + "╯", style=bs)

        self.console.print(t)

        # 提示信息
        hint = Text()
        hint.append("  Tips: ", style="dim")
        hint.append("/exit", style="bold")
        hint.append(" 退出  ", style="dim")
        hint.append("Ctrl+C", style="bold")
        hint.append(" 中断当前任务  ", style="dim")
        hint.append("-y", style="bold")
        hint.append(" 自动批准工具调用", style="dim")
        self.console.print(hint)
        self.console.print()

    # 不换行输出玩法，配合 LLM 的流式输出，可以实现增量渲染的效果
    def print_text_delta(self, text: str) -> None:
        self.console.print(text, end="")

    # 打印text，不换行
    def print_newline(self) -> None:
        self.console.print()
    # 打印工具调用（超长参数值截断到80字符）
    def print_tool_call(self, name: str, kwargs: dict) -> None:
        parts = []
        for k, v in kwargs.items():
            s = repr(v)
            if len(s) > 80:
                s = s[:80] + "..."
            parts.append(f"{k}={s}")
        args = ", ".join(parts)
        self.console.print(f"▶ {name}({args})", style=self.tool_style)
    # 打印工具调用结果 只输出前三行，每行最多200字符
    def print_tool_result_preview(self, result: str, max_line_chars: int = 200) -> None:
        lines = result.splitlines()
        preview = lines[:3]
        truncated_preview: list[str] = []
        for line in preview:
            if len(line) > max_line_chars:
                truncated_preview.append(line[:max_line_chars] + "…")
            else:
                truncated_preview.append(line)
        if truncated_preview:
            self.console.print("\n".join(truncated_preview), style=self.tool_style)
        remain = len(lines) - len(preview)
        if remain > 0:
            self.console.print(f"... ({remain} more lines)", style=self.tool_style)
