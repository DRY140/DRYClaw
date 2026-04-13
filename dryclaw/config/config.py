"""Stage 1 配置加载器：优先级 credentials.json > config.yaml > 环境变量。"""


from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import yaml
from pydantic_settings import BaseSettings, SettingsConfigDict


DRYCLAW_DIR = Path.home() / ".dryclaw"
CREDENTIALS_FILE = DRYCLAW_DIR / "credentials.json"
CONFIG_FILE = DRYCLAW_DIR / "config.yaml"


class DryclawConfig(BaseSettings):
    """与 Stage 1 对齐的最小配置模型。"""

    provider: str = "anthropic"
    api_key: str = ""
    api_base: str = ""
    model: str = "claude-haiku-4-5-20251001"
    max_iterations: int = 25
    context_window: int = 128000
    mcp_servers: list[dict[str, Any]] = []
    ax_server_path: str = "/path/to/ax_server"
    ax_server_mode: str = "socket"
    ax_server_socket_path: str = ""
    daemon_port: int = 7533

    model_config = SettingsConfigDict(
        env_prefix="",
        extra="ignore",
    )


def provider_env_defaults(provider: str) -> dict[str, str]:
    """根据 provider 选择环境变量底座。

    说明：
    1) Stage 1 兼容历史 Anthropic 变量。
    2) 新增 GLM 官方变量，便于无缝切换。
    """

    p = (provider or "").strip().lower()
    if p == "glm":
        return {
            "api_key": os.environ.get("ZAI_API_KEY", ""),
            "api_base": os.environ.get("ZAI_API_BASE", "https://open.bigmodel.cn/api/paas/v4/"),
        }
    if p == "openai":
        return {
            "api_key": os.environ.get("OPENAI_API_KEY", ""),
            "api_base": os.environ.get("OPENAI_BASE_URL", ""),
        }
    return {
        "api_key": os.environ.get("ANTHROPIC_API_KEY", ""),
        "api_base": os.environ.get("ANTHROPIC_BASE_URL", ""),
    }


def _load_yaml_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        return {}
    return data


def _load_json_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return {}
    return data


def _provider_block(data: dict[str, Any], provider: str) -> dict[str, Any]:
    """从 providers 节点读取指定 provider 的配置块。"""
    providers = data.get("providers")
    if not isinstance(providers, dict):
        return {}
    block = providers.get(provider)
    if not isinstance(block, dict):
        return {}
    return block


def _provider_default_model(provider: str) -> str:
    normalized = (provider or "").strip().lower()
    if normalized == "glm":
        return "glm-5"
    if normalized == "openai":
        return "gpt-4o-mini"
    return "claude-haiku-4-5-20251001"


def load_config(provider_override: str | None = None) -> DryclawConfig:
    """按固定优先级加载配置。

    中文说明：
    1) 先读环境变量作为最低优先级底座。
    2) 再读 config.yaml 覆盖底座。
    3) 最后读 credentials.json 作为最高优先级覆盖。
    """

    # 先读取文件原始数据，用于确定最终 provider。
    yaml_data = _load_yaml_file(CONFIG_FILE)
    creds_data = _load_json_file(CREDENTIALS_FILE)

    selected_provider = (
        (provider_override or "").strip().lower()
        or str(creds_data.get("provider", "")).strip().lower()
        or str(yaml_data.get("provider", "")).strip().lower()
        or "anthropic"
    )

    cfg_data: dict[str, Any] = {
        "provider": selected_provider,
        "model": _provider_default_model(selected_provider),
        "max_iterations": 25,
        "context_window": 128000,
        "mcp_servers": [],
        "ax_server_path": "/path/to/ax_server",
        "ax_server_mode": "socket",
        "ax_server_socket_path": "",
        "daemon_port": 7533,
        "api_key": "",
        "api_base": "",
    }

    # 最低优先级底座：按已选 provider 读取环境变量。
    cfg_data.update(provider_env_defaults(selected_provider))

    # 第二优先级（全局）：~/.dryclaw/config.yaml
    cfg_data.update(
        {
            "model": yaml_data.get("model", cfg_data["model"]),
            "api_key": yaml_data.get("api_key", cfg_data["api_key"]),
            "api_base": yaml_data.get("api_base", cfg_data["api_base"]),
            "max_iterations": yaml_data.get("max_iterations", cfg_data["max_iterations"]),
            "context_window": yaml_data.get("context_window", cfg_data["context_window"]),
            "mcp_servers": yaml_data.get("mcp_servers", cfg_data["mcp_servers"]),
            "ax_server_path": yaml_data.get("ax_server_path", cfg_data["ax_server_path"]),
            "ax_server_mode": yaml_data.get("ax_server_mode", cfg_data["ax_server_mode"]),
            "ax_server_socket_path": yaml_data.get("ax_server_socket_path", cfg_data["ax_server_socket_path"]),
            "daemon_port": yaml_data.get("daemon_port", cfg_data["daemon_port"]),
        }
    )

    # 第二优先级（provider 专属）：config.providers.<provider>
    yaml_provider = _provider_block(yaml_data, selected_provider)
    cfg_data.update(
        {
            "model": yaml_provider.get("model", cfg_data["model"]),
            "api_key": yaml_provider.get("api_key", cfg_data["api_key"]),
            "api_base": yaml_provider.get("api_base", cfg_data["api_base"]),
            "max_iterations": yaml_provider.get("max_iterations", cfg_data["max_iterations"]),
            "context_window": yaml_provider.get("context_window", cfg_data["context_window"]),
            "mcp_servers": yaml_provider.get("mcp_servers", cfg_data["mcp_servers"]),
            "ax_server_path": yaml_provider.get("ax_server_path", cfg_data["ax_server_path"]),
            "ax_server_mode": yaml_provider.get("ax_server_mode", cfg_data["ax_server_mode"]),
            "ax_server_socket_path": yaml_provider.get("ax_server_socket_path", cfg_data["ax_server_socket_path"]),
            "daemon_port": yaml_provider.get("daemon_port", cfg_data["daemon_port"]),
        }
    )

    # 最高优先级（全局）：~/.dryclaw/credentials.json
    cfg_data.update(
        {
            "model": creds_data.get("model", cfg_data["model"]),
            "api_key": creds_data.get("api_key", cfg_data["api_key"]),
            "api_base": creds_data.get("api_base", cfg_data["api_base"]),
            "max_iterations": creds_data.get("max_iterations", cfg_data["max_iterations"]),
            "context_window": creds_data.get("context_window", cfg_data["context_window"]),
            "mcp_servers": creds_data.get("mcp_servers", cfg_data["mcp_servers"]),
            "ax_server_path": creds_data.get("ax_server_path", cfg_data["ax_server_path"]),
            "ax_server_mode": creds_data.get("ax_server_mode", cfg_data["ax_server_mode"]),
            "ax_server_socket_path": creds_data.get("ax_server_socket_path", cfg_data["ax_server_socket_path"]),
            "daemon_port": creds_data.get("daemon_port", cfg_data["daemon_port"]),
        }
    )

    # 最高优先级（provider 专属）：credentials.providers.<provider>
    creds_provider = _provider_block(creds_data, selected_provider)
    cfg_data.update(
        {
            "model": creds_provider.get("model", cfg_data["model"]),
            "api_key": creds_provider.get("api_key", cfg_data["api_key"]),
            "api_base": creds_provider.get("api_base", cfg_data["api_base"]),
            "max_iterations": creds_provider.get("max_iterations", cfg_data["max_iterations"]),
            "context_window": creds_provider.get("context_window", cfg_data["context_window"]),
            "mcp_servers": creds_provider.get("mcp_servers", cfg_data["mcp_servers"]),
            "ax_server_path": creds_provider.get("ax_server_path", cfg_data["ax_server_path"]),
            "ax_server_mode": creds_provider.get("ax_server_mode", cfg_data["ax_server_mode"]),
            "ax_server_socket_path": creds_provider.get("ax_server_socket_path", cfg_data["ax_server_socket_path"]),
            "daemon_port": creds_provider.get("daemon_port", cfg_data["daemon_port"]),
        }
    )

    # 最终兜底：provider 对应环境变量补齐空值。
    env_selected = provider_env_defaults(selected_provider)
    if not cfg_data.get("api_key"):
        cfg_data["api_key"] = env_selected["api_key"]
    if not cfg_data.get("api_base"):
        cfg_data["api_base"] = env_selected["api_base"]

    return DryclawConfig.model_validate(cfg_data)


def masked_key(api_key: str) -> str:
    if not api_key:
        return "(not set)"
    if len(api_key) <= 8:
        return "*" * len(api_key)
    return f"***{api_key[-8:]}"


def config_source() -> str:
    if CREDENTIALS_FILE.exists():
        return "credentials.json"
    if CONFIG_FILE.exists():
        return "config.yaml"
    return "environment"


def check_auth_status(config: DryclawConfig | None = None) -> dict[str, str]:
    cfg = config or load_config()
    # packyapi 中转要求必须传 base_url，后续客户端会将该值映射到 SDK 的 base_url 参数。
    return {
        "provider": cfg.provider,
        "model": cfg.model,
        "api_base": cfg.api_base or "(default)",
        "api_key": masked_key(cfg.api_key),
        "source": config_source(),
    }
