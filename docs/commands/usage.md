# usage

Beautiful usage analytics, reports, timelines, model breakdowns and rough cost estimates.

```bash
grok-utils usage --help
```

## report

Generate a rich grouped usage report with visual share bars and sparklines.

```bash
grok-utils usage report --by project --top 8
grok-utils usage report --by model --since 2026-05-01 --json
grok-utils usage report --by day
```

**Options**

- `--since` — ISO date filter
- `--by` — `project` | `model` | `day` (default: project)
- `--top` — Show top N (default 10)
- `--json`

## top-projects

Leaderboard of projects by session count and activity.

```bash
grok-utils usage top-projects
grok-utils usage top-projects -n 15
```

## models

Model distribution and preferences.

```bash
grok-utils usage models
```

## timeline

Daily activity over the last N days (sparklines + counts).

```bash
grok-utils usage timeline --days 21
grok-utils usage timeline -d 90
```

## cost

Rough cost estimate using session message counts and static model pricing (proxy only — not exact billing).

```bash
grok-utils usage cost --by model
grok-utils usage cost --by project --top 5 --since 2026-05-01 --json
```

Useful for awareness and spotting expensive projects/models. Not a replacement for provider invoices.
