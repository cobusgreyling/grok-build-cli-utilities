# Command Reference

All commands live under the `grok-utils` CLI. Most have subcommands.

```bash
grok-utils --help
grok-utils <command> --help
grok-utils <command> <subcommand> --help
```

Every command that produces structured data supports `--json` (and the global `--grok-home` / `-g`).

Use the left navigation or the links below to jump to detailed docs for each command.

## Top-level

- [`doctor`](doctor.md) — Diagnose your Grok Build environment and grok-utils setup

## Full command groups

- [`sessions`](sessions.md) — Advanced session browser, search, stats, analyze, export, prune, resume
- [`skills`](skills.md) — Skill discovery, creation, validation, pack/unpack
- [`backup`](backup.md) — Industrial-strength, manifest-backed backup & restore
- [`usage`](usage.md) — Rich analytics, reports, timeline, models, cost estimates
- [`mcp`](mcp.md) — MCP server inspection, testing, example injection
- [`worktree`](worktree.md) — Git worktree + Grok session hygiene
- [`memory`](memory.md) — Cross-session memory explorer (experimental)
- [`plugins`](plugins.md) — Plugin discovery, inventory and validation
- [`hooks`](hooks.md) — Hooks listing, scaffolding and validation
- [`config`](config.md) — Inspect config.toml, paths, settings and validation
- [`logs`](logs.md) — Quick log tailing and filtering

See [Quick Start](../quickstart.md) for common usage patterns and [Examples & Tips](../examples.md) for more.
