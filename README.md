<p align="center">
  <img src="images/HjkMA.jpg" alt="Grok Build CLI Utilities" />
</p>

# grok-build-cli-utilities

[![CI](https://github.com/cobusgreyling/grok-build-cli-utilities/actions/workflows/ci.yml/badge.svg)](https://github.com/cobusgreyling/grok-build-cli-utilities/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/grok-build-cli-utilities.svg)](https://pypi.org/project/grok-build-cli-utilities/)
[![Docs](https://img.shields.io/badge/docs-GitHub%20Pages-blue?logo=gitbook&logoColor=white)](https://cobusgreyling.github.io/grok-build-cli-utilities/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)

**Amazing CLI utilities for [Grok Build](https://x.ai) by Cobus Greyling.**

A powerful, batteries-included collection of command-line tools that make you dramatically more productive with Grok Build.

- 12+ power commands (sessions, skills, backup, usage+cost, plugins, hooks, config, logs, mcp, worktree, memory, `doctor`)
- Beautiful rich terminal output (tables, progress, sparklines, bars)
- Safe-by-default (dry-run on anything destructive)
- Works directly against your real `~/.grok` data
- Scriptable with `--json`
- Zero-config — just works

**New in 0.3.1**: shared robust TOML loader (tomllib on 3.11+, tomli, improved naive), safe FS/JSON helpers, reduced broad exception handling, more tests + coverage, CI on macOS + build verification, `__main__` support, CODE_OF_CONDUCT, docs/CI polish, and bug fixes (e.g. plugin discovery).

**Sole author & maintainer:** Cobus Greyling

> **📖 Full documentation**: [https://cobusgreyling.github.io/grok-build-cli-utilities/](https://cobusgreyling.github.io/grok-build-cli-utilities/) — command reference, examples, philosophy and more.

---

## Installation

**Recommended (PyPI + pipx for isolation):**

```bash
# Best for CLI tools
pipx install grok-build-cli-utilities

# Or with pip
pip install grok-build-cli-utilities
```

**From source (latest development):**

```bash
git clone https://github.com/cobusgreyling/grok-build-cli-utilities.git
cd grok-build-cli-utilities
pip install -e ".[dev]"
# (or `python -m pip install -e ".[dev]"`)
```

The command `grok-utils` (and `python -m grok_build_cli_utilities`) will be available.

Verify:

```bash
grok-utils --version
grok-utils --help
grok-utils doctor
```

---

## The 7 Utilities + doctor

> **Tip:** Run `grok-utils doctor` for a quick health check of your Grok Build environment (works with `--grok-home` and `--json`).


### 1. `sessions` — Advanced session browser & manager

```bash
grok-utils sessions list --limit 20
grok-utils sessions list --project my-app --since 2026-05-20
grok-utils sessions search "auth middleware" --limit 10
grok-utils sessions info 019e87 --deep          # tool usage stats
grok-utils sessions stats
grok-utils sessions analyze 019e87
grok-utils sessions export 019e87 --format md -o session.md
grok-utils sessions resume 019e87             # or no arg = most recent in CWD
grok-utils sessions prune --older-than 60d --dry-run
```

- Fast summary-based listing (no heavy parsing until asked)
- Leverages Grok's own `session_search.sqlite` FTS when present
- Fallback content search across summaries
- Deep mode parses `updates.jsonl` for real tool call counts
- Safe prune with age + project filters (defaults to dry-run)

### 2. `skills` — Full skill lifecycle management

```bash
grok-utils skills list
grok-utils skills list --all
grok-utils skills create deploy --desc "Deploy services following our golden path"
grok-utils skills info deploy
grok-utils skills validate                 # all skills
grok-utils skills validate ./my-skill
grok-utils skills pack my-skill -o my-skill.skill.tar.gz
grok-utils skills unpack my-skill.skill.tar.gz --dest ~/.grok/skills
```

- Discovers skills from all locations (local, repo, user, claude/cursor compat) with correct priority
- Generates high-quality starter `SKILL.md` with frontmatter + structure
- Validates required fields, length, and content
- Pack/unpack for sharing or version control of skill collections

### 3. `backup` — Industrial-strength backup & restore

```bash
grok-utils backup create --include-sessions --projects "acme,personal"
grok-utils backup create -o ~/backups/grok-$(date +%F).tar.gz

grok-utils backup list

grok-utils backup restore ~/grok-backups/grok-backup-....tar.gz --dry-run
grok-utils backup restore ... --no-dry-run --force
```

- Always produces a manifest with SHA-256 hashes
- Selective session backup by project substring
- Core state always included: config, skills, user-settings, memory, plugins, etc.
- Restore is dry-run by default. Extremely safe.

### 4. `usage` — Stunning analytics & productivity insights

```bash
grok-utils usage report --by project --top 8
grok-utils usage report --by model --since 2026-05-01
grok-utils usage top-projects
grok-utils usage models
grok-utils usage timeline --days 21
```

- Grouped reports with visual share bars (`████░░░░`)
- Unicode sparklines for recent activity
- Daily timeline
- Model distribution
- JSON output for feeding into other tools or dashboards

### 5. `mcp` — MCP server superpowers

```bash
grok-utils mcp list
grok-utils mcp doctor
grok-utils mcp test my-github-server
grok-utils mcp add-example myfs --kind filesystem
```

- Parses `[mcp_servers]` from your `config.toml` (works even without tomli)
- Doctor checks PATH for commands
- Easy example injector for common servers (filesystem, GitHub, SQLite, ...)
- Delegates to `grok mcp ...` when helpful

### 6. `worktree` — Worktree + session hygiene

```bash
grok-utils worktree list
grok-utils worktree stats
grok-utils worktree prune-orphaned --dry-run
grok-utils worktree prune-orphaned --no-dry-run --yes
```

- Correlates `git worktree list` with your Grok sessions
- Finds "zombie" sessions pointing at deleted directories
- Great for heavy worktree users who spin up many Grok sessions

### 7. `memory` — Cross-session memory explorer (experimental support)

```bash
grok-utils memory list
grok-utils memory stats
grok-utils memory search "architecture decision"
grok-utils memory paths
```

Even if you don't have memory enabled yet, the tools are ready the moment you turn it on.

### New in this release (Tier 1/2)
```bash
grok-utils plugins list --all
grok-utils plugins inventory
grok-utils hooks list --event SessionStart
grok-utils hooks create PostToolUse my-audit
grok-utils config show
grok-utils config paths
grok-utils logs tail --level error -n 20
grok-utils usage cost --by model
grok-utils sessions export <id> --format html -o out.html
grok-utils sessions analyze <id>
```

These bring rich views for the maturing plugins/hooks ecosystem, cost awareness, and deep session forensics.

---

## Philosophy & Design

- **Sole author**: Every commit is by Cobus Greyling. No bots, no drive-by PRs, no other contributors.
- **Safe first**: Anything that can delete or overwrite defaults to `--dry-run`.
- **Beautiful & fast**: Rich tables, progress bars on big scans, instant on cached summaries.
- **Scriptable**: Every command that makes sense supports `--json`.
- **Real data only**: No mocks — these tools operate on your actual `~/.grok` layout.
- **Minimal deps**: Typer + Rich + Pydantic + a few small friends.

---

## Development

```bash
git clone https://github.com/cobusgreyling/grok-build-cli-utilities
cd grok-build-cli-utilities
pip install -e ".[dev]"

# Quality gates (CI runs the same)
make lint
make format   # or make lint after edits
make typecheck
make cov
# or simply: make test

# See Makefile for all targets (lint, cov, build, clean, etc.)
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for the full development guide, testing expectations, and how to propose changes.

---

## Screenshots & Examples

Real terminal output is best experienced live (`grok-utils usage report`, `sessions list`, `doctor`, etc.). Placeholder for future captured output:

<!-- TODO: add rich screenshots of tables, sparklines (████░░░░), progress, panels -->

## Roadmap (ideas)

**Many Tier 1/2 items implemented in this update** (plugins, hooks, sessions export/analyze, usage cost, config, logs, doctor expansions, deep parsers). See CHANGELOG.

### High priority (big productivity wins)
- `sessions resume <short-id>` — **done**.
- `sessions export <id>` — **done** (md/html/json).
- `plugins` subcommand — **done**.
- `hooks` subcommand — **done**.
- Cost estimation in usage — **done**.
- Rewind-preview / stronger diff (analyze covers some signals/rewinds).

### Analytics & cost
- Cost estimation + pricing in `usage` (model price table, `usage report --cost`, `usage cost --by project`). "Cost estimation using real model pricing".
- Deeper `sessions analyze <id>` (or `info --deep --full`) using `signals.json`, `plan.json`, compaction history, error rates, subagent trees, rewind stats.

### Session power tools
- Rewind / diff tooling: `sessions rewind-preview <id>`, `sessions diff <id1> <id2>` (what files/tokens/tools would change). "More powerful session rewind / diff tooling".
- `sessions compact-stats` or compaction insights.

### Other high-value
- `config` — inspect, validate, show effective (merged) config, key paths, get/set (dry-run + backup).
- Automatic / assisted skill extraction: `skills extract-from-session <id>` (headless grok assisted). "Automatic skill extraction from successful sessions".
- Logs & diagnostics: `logs tail`, `logs query "error" --since 1d` over `unified.jsonl`; integrate recent errors into `doctor`.
- Permissions/safety auditor: scan sessions for permission events, suggest rules or blocked actions.
- TUI dashboard mode (Textual) for live usage + session browser.

### Polish & ecosystem
- Fill screenshots in this README (rich tables, sparklines `████░░░░`, progress, panels).
- Project-rules / AGENTS.md linter + discovery (`rules lint`, `rules list`).
- Marketplace helpers (refresh, search) under `plugins marketplace`.
- Self-apply: add a `grok-utils-dev` skill for this repo's own development workflow.

This project is primarily maintainer-driven, but high-quality, well-tested contributions are welcome. Please read [CONTRIBUTING.md](CONTRIBUTING.md) first.

---

## License

MIT © 2026 Cobus Greyling

---

## Author

**Cobus Greyling**

- GitHub: [@cobusgreyling](https://github.com/cobusgreyling)
- Built for the Grok Build community

Enjoy the utilities!
