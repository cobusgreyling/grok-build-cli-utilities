# sessions

Advanced session browser, search, stats, deep analysis, export, safe prune and resume.

```bash
grok-utils sessions --help
```

## Subcommands

### list

List recent sessions with rich filters.

```bash
grok-utils sessions list --limit 20
grok-utils sessions list -l 50 --project my-app --since 2026-05-01
grok-utils sessions list --model "claude" --json
```

**Options**

- `--limit` / `-l` — Max sessions to show (default 30)
- `--project` / `-p` — Filter by substring in working directory
- `--model` / `-m` — Filter by current model ID
- `--since` — ISO date cutoff (e.g. 2026-05-20)
- `--json` — Structured output

Sessions are shown newest-first using last-active or created time.

### search

Full-text search across session transcripts (best-effort). Leverages Grok's `session_search.sqlite` FTS when present, falls back to scanning summaries.

```bash
grok-utils sessions search "auth middleware" --limit 10
grok-utils sessions search "tool loop" -l 5 --json
```

### info

Show detailed info for one session (prefix ID is accepted).

```bash
grok-utils sessions info 019e87
grok-utils sessions info 019e87 --deep
```

`--deep` parses `updates.jsonl` for real tool call counts and more stats (slower on very large sessions).

### stats

Quick aggregate stats over all sessions.

```bash
grok-utils sessions stats
```

### analyze

Deep analysis of a session using `signals.json` + rewind points + tool counts + plan info.

```bash
grok-utils sessions analyze 019e87
```

Great for understanding what happened in a long or problematic run.

### export

Export a session transcript/summary to markdown, simple self-contained HTML, or JSON.

```bash
grok-utils sessions export 019e87 --format md -o session.md
grok-utils sessions export 019e87 -f html -o review.html
grok-utils sessions export 019e87 --format json > session.json
```

Includes summary, signals, tool stats and basic rewind information.

### resume

Resume a session by delegating to the real `grok --resume`.

```bash
grok-utils sessions resume 019e87
grok-utils sessions resume          # most recent session for current working directory
```

The tool resolves short prefixes to the full session ID.

### prune

Prune old sessions (DANGEROUS — defaults to dry-run).

```bash
grok-utils sessions prune --older-than 90d --dry-run
grok-utils sessions prune --older-than 60d --project "temp" --no-dry-run --yes
```

**Options**

- `--older-than` — Age like `30d`, `2w`, `6mo`, `1y` (default 90d)
- `--project` — Only sessions whose CWD matches the substring
- `--dry-run` / `--no-dry-run` — Default safe: show what would be deleted
- `-y` / `--yes` — Skip confirmation prompt

Always review with `--dry-run` first.
