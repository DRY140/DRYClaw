from __future__ import annotations

import re
from enum import Enum


class Decision(str, Enum):
    ALLOW = "allow"
    DENY = "deny"
    ASK = "ask"


# 层1：硬封锁规则（命中即 DENY，不可绕过）
_HARD_DENY_PATTERNS = [
    re.compile(r"rm\s+-[rRf]{2,}\s+(?:/\s*$|~(?:/|\s*$))"),
    re.compile(r"dd\b.*\bof=/dev/"),
    re.compile(r"mkfs\b"),
    re.compile(r">\s*/dev/(sd|disk|nvme)"),
    re.compile(r"(curl|wget)\b.*\|\s*(ba)?sh"),
]


# 层2：安全命令前缀白名单（简化版，支持常见 150+ 场景的核心子集）
_SAFE_COMMAND_PREFIXES = [
    "pwd",
    "ls",
    "cat",
    "head",
    "tail",
    "wc",
    "echo",
    "printf",
    "which",
    "type",
    "file",
    "stat",
    "date",
    "env",
    "printenv",
    "whoami",
    "uname",
    "id",
    "ps",
    "top",
    "df",
    "du",
    "find",
    "grep",
    "rg",
    "awk",
    "sed",
    "cut",
    "sort",
    "uniq",
    "tr",
    "xargs",
    "python",
    "python3",
    "pytest",
    "pip list",
    "pip show",
    "git status",
    "git log",
    "git show",
    "git diff",
    "git branch",
    "git rev-parse",
    "git remote -v",
    "git ls-files",
    "git blame",
    "git grep",
    "make test",
    "make build",
    "npm test",
    "npm run test",
    "uv run",
]


def _split_compound_command(command: str) -> list[str]:
    # 复合命令拆分：对 &&、||、;、| 逐段检查，避免“安全命令 + 危险命令”串联绕过。
    parts = re.split(r"&&|\|\||;|\|", command)
    return [p.strip() for p in parts if p.strip()]


def _is_safe_prefix(command: str) -> bool:
    return any(command == p or command.startswith(f"{p} ") for p in _SAFE_COMMAND_PREFIXES)


class PermissionEngine:
    # 对bash命令进行判定
    def decide_for_bash(self, command: str) -> Decision:
        
        # 用黑名单进行匹配，发现命中则直接 DENY
        for pattern in _HARD_DENY_PATTERNS:
            if pattern.search(command):
                return Decision.DENY

        # 拆分合并的命令
        segments = _split_compound_command(command)

        # 如果有一个是黑名单的，那就deny
        for segment in segments:
            for pattern in _HARD_DENY_PATTERNS:
                if pattern.search(segment):
                    return Decision.DENY

        # 如果所有的段落都以安全前缀开头，则 ALLOW，否则 ASK
        if segments and all(_is_safe_prefix(segment) for segment in segments):
            return Decision.ALLOW
        return Decision.ASK

    # 对所有工具进行判定
    def decide_for_tool(self, tool_name: str, args: dict) -> Decision:
        name = tool_name.strip().lower()

        if name in {"file_read", "glob", "grep", "think", "session_search", "screenshot", "wait_for"}:
            return Decision.ALLOW

        if name in {
            "file_write",
            "file_edit",
            "memory_append",
            "clipboard",
            "notify",
            "browser",
            "accessibility",
            "computer",
        }:
            return Decision.ASK

        if name == "http":
            method = str(args.get("method", "GET")).upper()
            url = str(args.get("url", "")).lower()
            if method == "GET" and ("localhost" in url or "127.0.0.1" in url):
                return Decision.ALLOW
            return Decision.ASK

        if name == "bash":
            return self.decide_for_bash(str(args.get("command", "")))

        return Decision.ASK
