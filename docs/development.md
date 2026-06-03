# Development

## Setup

```bash
git clone https://github.com/cobusgreyling/grok-build-cli-utilities.git
cd grok-build-cli-utilities
pip install -e ".[dev]"
```

## Quality gates (CI runs exactly these)

```bash
make lint
make format          # or run lint after edits
make typecheck
make cov             # or make test
```

Or simply `make test`.

See the [Makefile](https://github.com/cobusgreyling/grok-build-cli-utilities/blob/main/Makefile) for all targets.

## Documentation

```bash
make docs-install
make docs-serve      # http://127.0.0.1:8000
make docs-build
```

The site is built with MkDocs + Material and automatically deployed to GitHub Pages on pushes to `main`.

## Pre-commit

```bash
make pre-commit
```

## Building & releasing

- CI builds and tests on every push/PR (macOS + Linux, Python 3.10–3.12).
- Release is tag-driven (`v*`): see `.github/workflows/release.yml`.
- PyPI trusted publishing is configured.

## Project layout (key paths)

- `src/grok_build_cli_utilities/` — the package
- `src/.../commands/*.py` — each subcommand group
- `src/.../utils/` — shared helpers, parsers, rich formatting
- `tests/` — pytest suite (good coverage expected for new code)
- `examples/sample-skill/` — reference skill
- `docs/` — this documentation site (MkDocs)

## Testing expectations

- New commands or major features need tests.
- Prefer real (but safe) filesystem operations over heavy mocking when possible.
- `--dry-run` paths and JSON output are especially important to cover.
- Run the full `make cov` locally before opening a PR.

## How to propose changes

Please read [CONTRIBUTING.md](https://github.com/cobusgreyling/grok-build-cli-utilities/blob/main/CONTRIBUTING.md) first. High-quality, focused PRs that follow the safety and style of the existing codebase are appreciated.

This is primarily a personal productivity toolkit — changes that increase complexity without clear productivity wins for the author are less likely to be accepted.
