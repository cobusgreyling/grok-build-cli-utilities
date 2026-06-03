# Quick Start

Run `grok-utils doctor` first — it gives you an instant overview of your Grok Build environment and what the utilities see.

```bash
grok-utils doctor
```

## Core workflows

### 1. Explore your sessions

```bash
# Recent activity
grok-utils sessions list --limit 20

# Filter by project or date
grok-utils sessions list --project acme --since 2026-05-01

# Search across transcripts (uses Grok's FTS when available)
grok-utils sessions search "auth" --limit 5

# Detailed view + tool usage
grok-utils sessions info 019e87 --deep
```

### 2. Analyze & export a session

```bash
# Deep forensics (signals + rewinds + tool counts)
grok-utils sessions analyze 019e87

# Export for sharing / notes / review
grok-utils sessions export 019e87 --format md -o my-session.md
grok-utils sessions export 019e87 --format html -o my-session.html
grok-utils sessions export 019e87 --format json -o my-session.json
```

### 3. Resume a session from the CLI

```bash
grok-utils sessions resume 019e87
# or the most recent one in current directory:
grok-utils sessions resume
```

This delegates to the real `grok --resume <full-id>`.

### 4. Skills

```bash
grok-utils skills list
grok-utils skills list --all   # include lower priority / compat locations

grok-utils skills create my-deploy --desc "Deploy following our golden path" --user

grok-utils skills info my-deploy
grok-utils skills validate my-deploy

# Share a skill
grok-utils skills pack my-deploy -o my-deploy.skill.tar.gz
grok-utils skills unpack my-deploy.skill.tar.gz --dest ~/.grok/skills
```

### 5. Backup & restore (extremely safe)

```bash
# Full backup (sessions optional, they can be large)
grok-utils backup create --include-sessions --projects "acme,personal"

# List your conventional backups
grok-utils backup list

# Preview a restore
grok-utils backup restore ~/grok-backups/backup-....tar.gz --dry-run

# Real restore (you are asked for confirmation unless --yes)
grok-utils backup restore ~/grok-backups/backup-....tar.gz --no-dry-run
```

Backups always include a SHA-256 manifest.

### 6. Usage analytics & cost awareness

```bash
grok-utils usage report --by project --top 8
grok-utils usage report --by model --since 2026-05-01

grok-utils usage top-projects
grok-utils usage models
grok-utils usage timeline --days 30

# Rough cost estimates (proxy using message counts + static pricing)
grok-utils usage cost --by model
grok-utils usage cost --by project
```

### 7. MCP, plugins, hooks, config

```bash
grok-utils mcp list
grok-utils mcp doctor
grok-utils mcp add-example myfs --kind filesystem   # then edit the generated block

grok-utils plugins list --all
grok-utils plugins inventory

grok-utils hooks list --event SessionStart
grok-utils hooks create PostToolUse my-audit

grok-utils config show
grok-utils config paths
grok-utils config validate

grok-utils logs tail --level error -n 20
```

See the individual command pages under **Commands** for every flag and option.

## Pro tips

- Almost every command that outputs data supports `--json`.
- Use `--grok-home` / `GROK_HOME` when working with secondary installations.
- Prune and restore are dry-run by default — you have to opt into destruction.
- `grok-utils doctor` is your friend after upgrades or when things feel off.
