# DRYClaw

Language: English | [中文](README.zh-CN.md)

DRYClaw is a Python AI agent CLI for terminal-first workflows, including file operations, shell execution, web interactions, scheduling, and daemon mode.

<img src="docs/assets/intro-ui.png" alt="DRYClaw CLI Preview" width="700" />

## Project Overview

- Lightweight CLI agent loop with tool calling
- Local session persistence and memory append support
- macOS-friendly automation helpers (including accessibility-based flow)
- Schedule and daemon commands for continuous workflows

## Installation

### Requirements

- Python 3.11+

### Install from source

```bash
git clone https://github.com/<your-username>/DRYClawV0-1-0.git
cd DRYClawV0-1-0
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Quick Start

```bash
dryclaw -p "用一句话介绍 DRYClaw"
```

Or run DRYClaw in interactive CLI mode:

```bash
cd DRYClawV0-1-0
source .venv/bin/activate
dryclaw
```

This starts a direct multi-turn conversation in the project CLI.

## Environment Configuration

DRYClaw reads local runtime configuration from the user home directory:

- `~/.dryclaw/config.yaml`
- `~/.dryclaw/credentials.json`

Do not commit real keys or private endpoints. Use templates in [examples/config.example.yaml](examples/config.example.yaml) and [examples/credentials.example.json](examples/credentials.example.json).

## CLI Usage

Common commands:

- `dryclaw --help`
- `dryclaw -p "..."`
- `dryclaw --provider anthropic --model claude-3-7-sonnet`
- `dryclaw --check-auth`
- `dryclaw schedule create --cron "*/5 * * * *" --prompt "..."`
- `dryclaw schedule list`
- `dryclaw schedule delete <id>`
- `dryclaw daemon start`
- `dryclaw daemon status`
- `dryclaw daemon stop`

Detailed docs are in [docs/](docs/index.md).

## Demo Videos

Video index: [docs/videos.md](docs/videos.md)

Recommended hosting:

- YouTube
- Bilibili
- GitHub Releases

## Acknowledgement and Source Notes

DRYClaw borrows design ideas and parts of dependency strategy from ShanClaw. We sincerely thank the ShanClaw team for their open-source work.

Important notes:

- `ax_server` related dependency and integration path are associated with ShanClaw.
- Before enabling related features, please verify applicable license terms and usage conditions.
- When redistributing components derived from external projects, keep required attribution and license notices.
