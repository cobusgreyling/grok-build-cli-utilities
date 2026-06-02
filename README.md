<p align="center">
  <img src="assets/header.png" alt="Grok Build CLI Utilities" width="160" />
</p>

# grok-build-cli-utilities

**Amazing CLI utilities for [Grok Build](https://x.ai) by Cobus Greyling.**

A powerful, batteries-included collection of command-line tools that make you dramatically more productive with Grok Build.

- 7 carefully crafted utilities
- Beautiful rich terminal output (tables, progress, sparklines, bars)
- Safe-by-default (dry-run on anything destructive)
- Works directly against your real `~/.grok` data
- Scriptable with `--json`
- Zero-config — just works

**Sole author & maintainer:** Cobus Greyling

---

## Installation

```bash
# From source (recommended while early)
git clone https://github.com/cobusgreyling/grok-build-cli-utilities.git
cd grok-build-cli-utilities
pip install -e ".[dev]"

# Or later when published
pip install grok-build-cli-utilities
```

The command `grok-utils` will be on your PATH.

Verify:

```bash
grok-utils --version
grok-utils --help
```

---

## The 7 Utilities

### 1. `sessions` — Advanced session browser & manager

```bash
grok-utils sessions list --limit 20
grok-utils sessions list --project my-app --since 2026-05-20
grok-utils sessions search "auth middleware" --limit 10
grok-utils sessions info 019e87 --deep          # tool usage stats
grok-utils sessions stats
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
pytest
ruff check .
```

---

## Roadmap (ideas)

- More powerful session rewind / diff tooling
- Cost estimation using real model pricing
- Export sessions to beautiful static HTML or Obsidian vaults
- Automatic skill extraction from successful sessions (headless grok assisted)
- TUI dashboard mode (Textual)

Pull requests from the maintainer only for now.

---

## License

MIT © 2026 Cobus Greyling

---

## Author

**Cobus Greyling**

- GitHub: [@cobusgreyling](https://github.com/cobusgreyling)
- Built for the Grok Build community

Enjoy the utilities!
