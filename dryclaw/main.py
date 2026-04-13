from __future__ import annotations

import asyncio
import os
import readline  # noqa: F401 — 导入即启用 input() 的光标移动和历史记录
import sys
import time
from pathlib import Path

import typer
from rich.console import Console

from dryclaw.agent.loop import AgentLoop
from dryclaw.config.config import check_auth_status, load_config
from dryclaw.daemon.server import daemon_status, start_daemon, stop_daemon
from dryclaw.mcp.client import MCPClientManager
from dryclaw.output.renderer import Renderer
from dryclaw.schedule.launchd import LaunchdScheduler
from dryclaw.session.store import save_session
from dryclaw.tools.accessibility import AccessibilityTool
from dryclaw.tools.bash import BashTool
from dryclaw.tools.clipboard import ClipboardTool
from dryclaw.tools.computer import ComputerTool
from dryclaw.tools.file_edit import FileEditTool
from dryclaw.tools.file_read import FileReadTool
from dryclaw.tools.file_write import FileWriteTool
from dryclaw.tools.glob_tool import GlobTool
from dryclaw.tools.grep_tool import GrepTool
from dryclaw.tools.http_tool import HttpTool
from dryclaw.tools.memory_tool import MemoryAppendTool
from dryclaw.tools.notify import NotifyTool
from dryclaw.tools.registry import ToolRegistry
from dryclaw.tools.screenshot import ScreenshotTool
from dryclaw.tools.session_search import SessionSearchTool
from dryclaw.tools.think import ThinkTool
from dryclaw.tools.wait_for import WaitForTool


app = typer.Typer(
    add_completion=False,
    invoke_without_command=True,
    context_settings={"allow_extra_args": True},
)
console = Console()


def build_stage2_registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(FileReadTool())
    registry.register(GrepTool())
    registry.register(GlobTool())
    registry.register(ThinkTool())
    registry.register(FileWriteTool())
    registry.register(FileEditTool())
    registry.register(BashTool())
    registry.register(HttpTool())
    registry.register(MemoryAppendTool())
    registry.register(SessionSearchTool())
    registry.register(NotifyTool())
    registry.register(ClipboardTool())
    registry.register(ScreenshotTool())
    registry.register(AccessibilityTool())
    registry.register(ComputerTool())
    registry.register(WaitForTool())
    return registry


schedule_app = typer.Typer(add_completion=False, help="Stage3 launchd scheduler commands")
app.add_typer(schedule_app, name="schedule")
daemon_app = typer.Typer(add_completion=False, help="Stage4 daemon commands")
app.add_typer(daemon_app, name="daemon")


@schedule_app.command("create")
def schedule_create(
    cron: str = typer.Option(..., "--cron", help="Cron expression, e.g. */1 * * * *"),
    prompt: str = typer.Option(..., "--prompt", help="Prompt to run with dryclaw -y"),
    name: str = typer.Option("", "--name", help="Optional schedule id"),
) -> None:
    scheduler = LaunchdScheduler()
    item = scheduler.create(cron_expr=cron, prompt=prompt, name=name)
    console.print(f"created: {item.id}")
    console.print(f"plist: {item.plist}")


@schedule_app.command("list")
def schedule_list() -> None:
    scheduler = LaunchdScheduler()
    items = scheduler.list()
    if not items:
        console.print("no schedules")
        return
    for item in items:
        console.print(f"{item.id} | {item.cron} | {item.plist}")


@schedule_app.command("delete")
def schedule_delete(schedule_id: str = typer.Argument(..., help="schedule id")) -> None:
    scheduler = LaunchdScheduler()
    ok = scheduler.delete(schedule_id)
    if ok:
        console.print(f"deleted: {schedule_id}")
    else:
        console.print(f"not found: {schedule_id}")


@daemon_app.command("start")
def daemon_start(port: int = typer.Option(7533, "--port", help="Daemon HTTP port")) -> None:
    console.print(f"daemon starting on 127.0.0.1:{port}")
    start_daemon(port=port)


@daemon_app.command("stop")
def daemon_stop() -> None:
    ok = stop_daemon()
    if ok:
        console.print("daemon stopped")
    else:
        console.print("daemon not running")


@daemon_app.command("status")
def daemon_status_cmd(port: int = typer.Option(7533, "--port", help="Daemon HTTP port")) -> None:
    status = daemon_status(port=port)
    console.print(f"pid_file: {status['pid_file']}")
    console.print(f"health: {status['health']}")


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    prompt: str | None = typer.Option(None, "--prompt", "-p", help="User prompt"),
    provider: str | None = typer.Option(None, "--provider", help="Override provider: anthropic|glm|openai"),
    model: str | None = typer.Option(None, "--model", help="Override model"),
    cwd: str | None = typer.Option(None, "--cwd", help="Working directory"),
    check_auth: bool = typer.Option(False, "--check-auth", help="Check current auth config"),
    yes: bool = typer.Option(False, "-y", "--yes", help="Auto approve ASK-level actions"),
) -> None:
    if ctx.invoked_subcommand:
        return

    if prompt is None and ctx.args:
        prompt = " ".join(ctx.args).strip()

    config = load_config(provider_override=provider)

    if provider:
        chosen = provider.strip().lower()
        if chosen not in {"anthropic", "glm", "openai"}:
            console.print("ERROR: --provider must be one of: anthropic, glm, openai")
            raise typer.Exit(code=1)
        config.provider = chosen

    if model:
        config.model = model

    if cwd:
        os.chdir(Path(cwd).expanduser())

    if check_auth:
        status = check_auth_status(config)
        console.print(f"provider: {status['provider']}")
        console.print(f"model: {status['model']}")
        console.print(f"api_base: {status['api_base']}")
        console.print(f"api_key: {status['api_key']}")
        console.print(f"source: {status['source']}")

        from dryclaw.client.llm import LLMClient

        start = time.perf_counter()
        ok, detail = LLMClient(config).check_auth()
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        console.print(f"latency_ms: {elapsed_ms}")
        console.print(f"auth_ok: {ok}")
        if not ok:
            console.print(f"auth_detail: {detail}")
        raise typer.Exit(code=0)

    # 创建 AgentLoop
    registry = build_stage2_registry()
    mcp_manager = MCPClientManager()
    mcp_manager.load_from_config(config.mcp_servers)
    mcp_manager.refresh_tools(registry)

    loop = AgentLoop(config=config, tools=registry, auto_approve=yes)

    # 单次执行模式：有 -p 参数
    if prompt:
        _run_single(loop, prompt)
        raise typer.Exit(code=0)

    # REPL 交互模式：无参数启动
    _run_repl(loop, config)


def _run_single(loop: AgentLoop, prompt: str) -> None:
    """单次执行模式（兼容旧行为）。"""
    answer = asyncio.run(loop.run(prompt))
    session_path = save_session(cwd=str(Path.cwd()), messages=loop.history)
    console.print(f"\n[session] {session_path}")


def _run_repl(loop: AgentLoop, config: object) -> None:
    """REPL 多轮对话模式。"""
    renderer = Renderer()
    renderer.print_welcome(
        version="0.1.0",
        provider=getattr(config, "provider", ""),
        model=getattr(config, "model", ""),
        cwd=str(Path.cwd()),
    )

    # ANSI 着色的输入提示（蓝色加粗，匹配方案B配色）
    prompt_str = "\033[1;38;5;75mYou >\033[0m "

    turn = 0
    while True:
        # 读取用户输入
        try:
            user_input = input(prompt_str).strip()
        except (EOFError, KeyboardInterrupt):
            # Ctrl+D 或 Ctrl+C 退出
            console.print("\n[dim]Goodbye![/dim]")
            break

        if not user_input:
            continue

        # 内置命令
        if user_input.lower() in {"/exit", "/quit", "exit", "quit"}:
            console.print("[dim]Goodbye![/dim]")
            break

        if user_input.lower() in {"/help"}:
            console.print("[dim]  /exit   - 退出[/dim]")
            console.print("[dim]  /clear  - 清除对话历史，开始新会话[/dim]")
            console.print("[dim]  /save   - 保存当前会话[/dim]")
            console.print("[dim]  Ctrl+C  - 中断当前任务[/dim]")
            continue

        if user_input.lower() in {"/clear"}:
            # 保存旧会话，然后清空
            if loop.history:
                session_path = save_session(cwd=str(Path.cwd()), messages=loop.history)
                console.print(f"[dim]会话已保存: {session_path}[/dim]")
            loop.history.clear()
            turn = 0
            console.print("[dim]对话历史已清除，开始新会话。[/dim]")
            continue

        if user_input.lower() in {"/save"}:
            if loop.history:
                session_path = save_session(cwd=str(Path.cwd()), messages=loop.history)
                console.print(f"[dim]会话已保存: {session_path}[/dim]")
            else:
                console.print("[dim]暂无对话历史。[/dim]")
            continue

        # 执行对话
        turn += 1
        loop.reset_for_new_turn()

        try:
            asyncio.run(loop.run(user_input))
        except KeyboardInterrupt:
            console.print("\n[dim]任务已中断。[/dim]")
            continue
        except Exception as exc:
            console.print(f"[red]ERROR: {exc}[/red]")
            continue

        console.print()  # 每轮之间空一行

    # 退出时自动保存会话
    if loop.history:
        session_path = save_session(cwd=str(Path.cwd()), messages=loop.history)
        console.print(f"[dim]会话已保存: {session_path}[/dim]")


if __name__ == "__main__":
    app()
