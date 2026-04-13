from __future__ import annotations

import asyncio
import json
import os
import signal
from pathlib import Path
from typing import Any

import httpx
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse

from dryclaw.agent.loop import AgentLoop
from dryclaw.config.config import load_config
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


DAEMON_DIR = Path.home() / ".dryclaw"
DAEMON_PID = DAEMON_DIR / "daemon.pid"


class DaemonState:
    def __init__(self, max_concurrency: int = 5) -> None:
        self.semaphore = asyncio.Semaphore(max_concurrency)
        self.max_concurrency = max_concurrency
        self.current_running = 0
        self.completed = 0
        self.events: asyncio.Queue[str] = asyncio.Queue()


state = DaemonState(max_concurrency=5)
app = FastAPI(title="dryclaw-daemon")


def build_registry() -> ToolRegistry:
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


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/status")
async def status() -> dict[str, Any]:
    return {
        "status": "ok",
        "current_running": state.current_running,
        "max_concurrency": state.max_concurrency,
        "completed": state.completed,
    }


@app.post("/message")
async def message(payload: dict[str, Any]) -> dict[str, Any]:
    prompt = str(payload.get("prompt", "")).strip()
    mock = bool(payload.get("mock", False))
    mock_delay = float(payload.get("delay", 0.0) or 0.0)
    if not prompt:
        raise HTTPException(status_code=400, detail="missing prompt")

    async with state.semaphore:
        state.current_running += 1
        await state.events.put(json.dumps({"type": "start", "prompt": prompt}, ensure_ascii=False))
        try:
            if mock:
                if mock_delay > 0:
                    await asyncio.sleep(mock_delay)
                answer = f"mock:{prompt}"
            else:
                cfg = load_config()
                registry = build_registry()
                loop = AgentLoop(config=cfg, tools=registry, auto_approve=True)
                answer = await loop.run(prompt)
            state.completed += 1
            await state.events.put(json.dumps({"type": "done", "prompt": prompt}, ensure_ascii=False))
            return {"ok": True, "answer": answer}
        finally:
            state.current_running -= 1


@app.get("/events")
async def events() -> StreamingResponse:
    async def gen():
        while True:
            try:
                data = await asyncio.wait_for(state.events.get(), timeout=15)
                yield f"data: {data}\n\n"
            except TimeoutError:
                yield "data: {\"type\": \"heartbeat\"}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")


@app.post("/config/reload")
async def config_reload() -> dict[str, Any]:
    cfg = load_config()
    return {"status": "ok", "provider": cfg.provider, "model": cfg.model}


def start_daemon(port: int = 7533) -> None:
    DAEMON_DIR.mkdir(parents=True, exist_ok=True)
    DAEMON_PID.write_text(str(os.getpid()), encoding="utf-8")
    try:
        uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")
    finally:
        if DAEMON_PID.exists():
            DAEMON_PID.unlink(missing_ok=True)


def stop_daemon() -> bool:
    if not DAEMON_PID.exists():
        return False
    try:
        pid = int(DAEMON_PID.read_text(encoding="utf-8").strip())
        os.kill(pid, signal.SIGTERM)
        DAEMON_PID.unlink(missing_ok=True)
        return True
    except Exception:
        return False


def daemon_status(port: int = 7533) -> dict[str, Any]:
    running = DAEMON_PID.exists()
    health = None
    try:
        with httpx.Client(timeout=2.0) as client:
            resp = client.get(f"http://127.0.0.1:{port}/health")
            health = resp.json() if resp.status_code == 200 else {"status": "down"}
    except Exception:
        health = {"status": "down"}
    return {"pid_file": running, "health": health}
