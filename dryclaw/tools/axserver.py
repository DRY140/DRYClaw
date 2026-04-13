from __future__ import annotations

import json
import select
import socket
import subprocess
import tempfile
import threading
import time
from pathlib import Path
from typing import Any


class AXServerClient:
    """ax_server IPC client.

    Priority order:
    1) Unix socket mode (`--socket`) when configured.
    2) stdio JSONL fallback.
    """

    def __init__(self, binary_path: str, mode: str = "socket", socket_path: str = "") -> None:
        self.binary_path = str(binary_path).strip()
        self.mode = str(mode or "socket").strip().lower()
        self.socket_path = str(socket_path).strip()
        self._proc: subprocess.Popen[str] | None = None
        self._sock: socket.socket | None = None
        self._sock_file = None
        self._effective_mode: str = "stdio"
        self._tmp_socket_path: str | None = None
        self._lock = threading.Lock()
        self._seq = 0

    def _next_id(self) -> int:
        self._seq += 1
        return self._seq

    @staticmethod
    def _normalize_response(raw: dict[str, Any]) -> dict[str, Any]:
        if "error" in raw and raw.get("error") is not None:
            err = raw.get("error")
            if isinstance(err, dict):
                return {
                    "ok": False,
                    "id": raw.get("id"),
                    "error": str(err.get("message", "unknown error")),
                    "error_code": err.get("code"),
                    "raw": raw,
                }
            return {"ok": False, "id": raw.get("id"), "error": str(err), "raw": raw}

        if "result" in raw:
            result = raw.get("result")
            if isinstance(result, dict):
                if "ok" not in result:
                    result = {"ok": True, **result}
                return result
            return {"ok": True, "result": result, "id": raw.get("id")}

        # Backward-compatible branch for servers returning plain dict payload.
        if "ok" in raw:
            return raw
        return {"ok": True, **raw}

    @staticmethod
    def _legacy_to_method(cmd: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        action = str(cmd.get("action", "")).strip().lower()
        if action == "get_elements":
            params = {"pid": cmd.get("pid")}
            return "read_tree", {k: v for k, v in params.items() if v is not None}
        if action == "click_element":
            path = cmd.get("ref") or cmd.get("path")
            params = {"pid": cmd.get("pid"), "path": path, "expected_role": cmd.get("expected_role")}
            return "click", {k: v for k, v in params.items() if v not in (None, "")}
        if action == "type_text":
            params = {"value": cmd.get("text") or cmd.get("value") or ""}
            return "type_text", params
        if action == "click":
            params = {
                "type": "click",
                "x": cmd.get("x"),
                "y": cmd.get("y"),
                "button": "left",
                "clicks": 1,
            }
            return "mouse_event", {k: v for k, v in params.items() if v is not None}
        if action == "double_click":
            params = {
                "type": "click",
                "x": cmd.get("x"),
                "y": cmd.get("y"),
                "button": "left",
                "clicks": 2,
            }
            return "mouse_event", {k: v for k, v in params.items() if v is not None}
        if action == "right_click":
            params = {
                "type": "click",
                "x": cmd.get("x"),
                "y": cmd.get("y"),
                "button": "right",
                "clicks": 1,
            }
            return "mouse_event", {k: v for k, v in params.items() if v is not None}
        if action == "move":
            params = {"type": "move", "x": cmd.get("x"), "y": cmd.get("y")}
            return "mouse_event", {k: v for k, v in params.items() if v is not None}
        if action == "key":
            params = {
                "key": cmd.get("key") or cmd.get("key_combination") or "",
                "modifiers": cmd.get("modifiers") or [],
            }
            return "key_event", params
        if action == "type":
            return "type_text", {"value": cmd.get("text") or ""}
        if action == "scroll":
            direction = str(cmd.get("direction", "down")).strip().lower()
            amount = int(cmd.get("amount", 1) or 1)
            dy = amount if direction == "down" else -amount
            return "scroll", {"dx": 0, "dy": dy}
        return action or "ping", {k: v for k, v in cmd.items() if k != "action"}

    def _ensure_socket_path(self) -> str:
        if self.socket_path:
            return self.socket_path
        if self._tmp_socket_path:
            return self._tmp_socket_path
        self._tmp_socket_path = tempfile.mktemp(prefix="dryclaw_ax_", suffix=".sock")
        return self._tmp_socket_path

    def _start_socket(self, path: Path) -> tuple[bool, str]:
        socket_path = self._ensure_socket_path()
        try:
            self._proc = subprocess.Popen(
                [str(path), "--socket", socket_path],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
            )
        except Exception as exc:
            self._proc = None
            return False, f"failed to start ax_server in socket mode: {exc}"

        assert self._proc is not None
        if self._proc.stdout is None:
            self.stop()
            return False, "ax_server socket mode stdout unavailable"

        deadline = time.time() + 5.0
        fd = self._proc.stdout.fileno()
        while time.time() < deadline:
            ready, _, _ = select.select([fd], [], [], 0.2)
            if not ready:
                if self._proc.poll() is not None:
                    break
                continue
            line = self._proc.stdout.readline().strip()
            if line == "ready":
                break

        if self._proc.poll() is not None:
            self.stop()
            return False, "ax_server exited before socket became ready"

        try:
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.settimeout(6.0)
            sock.connect(socket_path)
            self._sock = sock
            self._sock_file = sock.makefile("r", encoding="utf-8", newline="\n")
            self._effective_mode = "socket"
            return True, f"started(socket): {path}"
        except Exception as exc:
            self.stop()
            return False, f"failed to connect ax_server socket: {exc}"

    def _start_stdio(self, path: Path) -> tuple[bool, str]:
        try:
            self._proc = subprocess.Popen(
                [str(path)],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
            )
            self._effective_mode = "stdio"
            return True, f"started(stdio): {path}"
        except Exception as exc:
            self._proc = None
            return False, f"failed to start ax_server: {exc}"

    def start(self) -> tuple[bool, str]:
        if self._proc is not None and self._proc.poll() is None:
            return True, "already started"

        if not self.binary_path:
            return False, "ax_server path is empty"

        path = Path(self.binary_path).expanduser()
        if not path.exists():
            return False, f"ax_server not found: {path}"

        if self.mode == "socket":
            ok, detail = self._start_socket(path)
            if ok:
                return ok, detail

        return self._start_stdio(path)

    def stop(self) -> None:
        with self._lock:
            if self._sock_file is not None:
                try:
                    self._sock_file.close()
                except Exception:
                    pass
                self._sock_file = None
            if self._sock is not None:
                try:
                    self._sock.close()
                except Exception:
                    pass
                self._sock = None
            if self._proc is None:
                return
            try:
                self._proc.terminate()
                self._proc.wait(timeout=3)
            except Exception:
                try:
                    self._proc.kill()
                except Exception:
                    pass
            finally:
                self._proc = None

    def _send_stdio(self, payload: str, timeout: float) -> dict[str, Any]:
        assert self._proc is not None
        if self._proc.stdin is None or self._proc.stdout is None:
            return {"ok": False, "error": "ax_server stdio unavailable"}

        self._proc.stdin.write(payload + "\n")
        self._proc.stdin.flush()

        deadline = time.time() + timeout
        fd = self._proc.stdout.fileno()
        while time.time() < deadline:
            ready, _, _ = select.select([fd], [], [], 0.2)
            if not ready:
                continue
            line = self._proc.stdout.readline().strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                if isinstance(data, dict):
                    return self._normalize_response(data)
            except Exception:
                return {"ok": False, "error": f"invalid ax_server response: {line}"}
        return {"ok": False, "error": "ax_server timeout"}

    def _send_socket(self, payload: str, timeout: float) -> dict[str, Any]:
        if self._sock is None or self._sock_file is None:
            return {"ok": False, "error": "ax_server socket unavailable"}

        self._sock.settimeout(timeout)
        self._sock.sendall((payload + "\n").encode("utf-8"))
        line = self._sock_file.readline()
        if not line:
            return {"ok": False, "error": "ax_server socket disconnected"}
        line = line.strip()
        try:
            data = json.loads(line)
            if isinstance(data, dict):
                return self._normalize_response(data)
            return {"ok": False, "error": f"unexpected ax_server response: {line}"}
        except Exception:
            return {"ok": False, "error": f"invalid ax_server response: {line}"}

    def send_command(
        self,
        cmd_or_method: dict[str, Any] | str,
        params: dict[str, Any] | None = None,
        timeout: float = 8.0,
    ) -> dict[str, Any]:
        with self._lock:
            ok, detail = self.start()
            if not ok:
                return {"ok": False, "error": detail}

            try:
                if isinstance(cmd_or_method, dict):
                    if "method" in cmd_or_method:
                        request = {
                            "id": int(cmd_or_method.get("id", self._next_id())),
                            "method": str(cmd_or_method.get("method", "ping")),
                            "params": cmd_or_method.get("params") or {},
                        }
                    else:
                        method, mapped_params = self._legacy_to_method(cmd_or_method)
                        request = {"id": self._next_id(), "method": method, "params": mapped_params}
                else:
                    request = {
                        "id": self._next_id(),
                        "method": str(cmd_or_method).strip() or "ping",
                        "params": params or {},
                    }

                payload = json.dumps(request, ensure_ascii=False)
                if self._effective_mode == "socket":
                    return self._send_socket(payload, timeout)
                return self._send_stdio(payload, timeout)
            except Exception as exc:
                return {"ok": False, "error": f"ax_server command failed: {exc}"}
