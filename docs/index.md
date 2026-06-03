# grok-utils

<p align="center">
  <img src="assets/header.jpg" alt="Grok Build CLI Utilities" width="420" />
</p>

**Powerful CLI utilities for [Grok Build](https://x.ai) by Cobus Greyling.**

A batteries-included collection of command-line power tools that make you dramatically more productive with Grok Build.

[![PyPI](https://img.shields.io/pypi/v/grok-build-cli-utilities.svg)](https://pypi.org/project/grok-build-cli-utilities/)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![GitHub](https://img.shields.io/badge/GitHub-cobusgreyling%2Fgrok--build--cli--utilities-blue?logo=github)](https://github.com/cobusgreyling/grok-build-cli-utilities)

---

## Why grok-utils?

- **12+ power commands**: `sessions`, `skills`, `backup`, `usage` (+ cost), `plugins`, `hooks`, `config`, `logs`, `mcp`, `worktree`, `memory`, and the top-level `doctor`
- **Beautiful terminal output**: Rich tables, progress bars, sparklines (`████░░░░`), panels
- **Safe by default**: Destructive operations default to `--dry-run`
- **Real data**: Operates directly on your `~/.grok` (or `$GROK_HOME`)
- **Scriptable**: `--json` on almost everything
- **Zero config**: Just works

**Sole author & maintainer:** [Cobus Greyling](https://github.com/cobusgreyling)

---

## The Commands at a Glance

| Command     | Description                                      |
|-------------|--------------------------------------------------|
| `doctor`    | Health check your Grok Build + grok-utils setup |
| `sessions`  | List, search, analyze, export, prune, resume sessions |
| `skills`    | Discover, create, validate, pack/unpack skills  |
| `backup`    | Safe, manifest-backed backup & restore          |
| `usage`     | Analytics: reports, models, timeline, cost estimates |
| `mcp`       | Inspect, test, add examples for MCP servers     |
| `worktree`  | Correlate git worktrees with Grok sessions      |
| `memory`    | Explore cross-session memory (experimental)     |
| `plugins`   | Discover & validate plugins                     |
| `hooks`     | List, scaffold, validate hooks                  |
| `config`    | Inspect config.toml, paths, validate            |
| `logs`      | Tail Grok logs with level filters               |

> **Quick tip:** Run `grok-utils doctor` first to see the state of your environment.

---

## Installation

The recommended way:

```bash
pipx install grok-build-cli-utilities
```

Or with pip:

```bash
pip install grok-build-cli-utilities
```

See the [Installation](installation.md) page for source install, verification, and pipx recommendations.

---

## Quick Example

```bash
# Health check
grok-utils doctor

# Browse sessions
grok-utils sessions list --limit 10 --project my-app

# Deep analysis of a session
grok-utils sessions analyze 019e87

# Export a session
grok-utils sessions export 019e87 --format html -o session.html

# Usage analytics + cost
grok-utils usage report --by project --top 5
grok-utils usage cost --by model

# Skill scaffolding
grok-utils skills create deploy --desc "Deploy services following our golden path"

# Safe backup
grok-utils backup create --include-sessions
```

Full details in [Quick Start](quickstart.md) and per-command pages.

---

## Philosophy

- **Safe first** — dry-run is the default for anything destructive.
- **Beautiful & fast** — instant cached summaries, rich visuals.
- **Scriptable** — JSON everywhere it makes sense.
- **Real data only** — no mocks.
- **Minimal deps** — Typer + Rich + Pydantic + friends.

See [Philosophy & Design](philosophy.md).

---

## Links

- **GitHub**: [cobusgreyling/grok-build-cli-utilities](https://github.com/cobusgreyling/grok-build-cli-utilities)
- **PyPI**: [grok-build-cli-utilities](https://pypi.org/project/grok-build-cli-utilities/)
- **Issues & Roadmap**: [GitHub Issues](https://github.com/cobusgreyling/grok-build-cli-utilities/issues)
- **Changelog**: [CHANGELOG.md](changelog.md) (and in the nav)

Enjoy the utilities!
