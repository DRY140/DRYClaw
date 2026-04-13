# CLI Reference

## Help

```bash
dryclaw --help
```

## Prompt Input

```bash
dryclaw --prompt "总结一下这个仓库"
# short form
dryclaw -p "总结一下这个仓库"
```

## Provider Override

```bash
dryclaw --provider anthropic
```

## Model Override

```bash
dryclaw --model claude-3-7-sonnet
```

## Check Auth

```bash
dryclaw --check-auth
```

## Schedule

```bash
dryclaw schedule create --cron "*/5 * * * *" --prompt "执行一次检查"
dryclaw schedule list
dryclaw schedule delete <schedule-id>
```

## Daemon

```bash
dryclaw daemon start
dryclaw daemon status
dryclaw daemon stop
```
