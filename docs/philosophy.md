# Philosophy & Design

This project is **maintainer-driven** (sole author: Cobus Greyling). High-quality, well-tested contributions are welcome after reading [CONTRIBUTING.md](https://github.com/cobusgreyling/grok-build-cli-utilities/blob/main/CONTRIBUTING.md).

## Core principles

- **Safe first** — Anything that can delete or overwrite defaults to `--dry-run`. You must explicitly opt in.
- **Beautiful & fast** — Rich tables, progress on big scans, instant results on cached summaries. No heavy parsing until you ask for `--deep`.
- **Scriptable** — Every command that makes sense supports `--json`.
- **Real data only** — These tools operate exclusively on your actual `~/.grok` layout. No mocks in the main paths.
- **Minimal dependencies** — Typer + Rich + Pydantic + a few small, well-chosen friends (pyyaml, dateutil, tomli on <3.11).
- **Zero config** — The utilities discover everything they need.

## Non-goals

- Do not become a full TUI (there is already a great Grok TUI).
- Do not duplicate core `grok` functionality — we delegate or complement where sensible (`resume`, some MCP).
- Do not add heavy ML / analytics frameworks; stay lightweight and terminal-native.

See the main [README](https://github.com/cobusgreyling/grok-build-cli-utilities) for the current roadmap of high-value ideas.
