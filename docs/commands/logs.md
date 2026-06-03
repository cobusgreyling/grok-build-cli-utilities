# logs

Quick log tailing and level filtering over Grok's unified logs.

```bash
grok-utils logs --help
```

## tail

Show the last N log lines (optionally filtered by level).

```bash
grok-utils logs tail --lines 30
grok-utils logs tail -n 100 --level error
grok-utils logs tail -l warn --json
```

**Options**

- `--lines` / `-n` — Number of lines (default 30)
- `--level` / `-l` — `error` | `info` | `warn`
- `--json` — Emit raw JSON lines when available

Useful for quickly surfacing recent errors without opening the log files directly.
