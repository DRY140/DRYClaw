# Environment Configuration

## Provider Configuration

Configure model provider through user config files and environment variables.

## Environment Variables

Typical variables include API key and optional API base URL from your provider setup.

## Local Config Files

DRYClaw loads user-level config from:

- `~/.dryclaw/config.yaml`
- `~/.dryclaw/credentials.json`

These files are local runtime files and must not be committed to this repository.

## Config Priority

Current documented priority:

- `credentials.json` > `config.yaml` > environment variables

## `ax_server` External Dependency

`ax_server` integration is an external dependency path associated with ShanClaw.

Before enabling this dependency:

- Verify license compatibility
- Verify redistribution conditions
- Keep required attribution or NOTICE information

## ShanClaw Source Note

DRYClaw borrows ideas and partial dependency design from ShanClaw. Thanks to the ShanClaw open-source maintainers and contributors.
