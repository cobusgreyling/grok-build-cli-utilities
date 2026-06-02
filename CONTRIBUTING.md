# Contributing to grok-build-cli-utilities

Thank you for your interest in improving grok-build-cli-utilities!

This is a maintainer-driven project focused on high-quality, safe CLI tools for Grok Build users. Contributions that follow the guidelines below are very welcome (bug reports, feature ideas, docs improvements, and well-tested code changes).

## Code of Conduct

Be respectful and constructive. This is a small, focused tool for the Grok Build community.

## Development Setup

```bash
git clone https://github.com/cobusgreyling/grok-build-cli-utilities.git
cd grok-build-cli-utilities
python -m pip install -e ".[dev]"
```

## Quality Bar (required before any PR)

Run these and ensure they pass:

```bash
ruff check .
ruff format --check .
mypy src/grok_build_cli_utilities --ignore-missing-imports
pytest -q --cov=src/grok_build_cli_utilities --cov-report=term-missing
```

The GitHub Actions CI runs the exact same checks on every push and PR (Python 3.10–3.12).

## Testing

- All new code must be accompanied by tests.
- Use `tmp_path` (pytest) + `--grok-home` overrides or monkeypatching for filesystem-dependent commands.
- Prefer testing the happy path + the security/error paths (e.g. bad tar members, invalid skills, prune dry-run).
- Run the full suite locally before pushing.

## Commit Style

- Use conventional-ish messages: `fix:`, `feat:`, `docs:`, `test:`, `chore:`, `refactor:`.
- Keep commits focused and atomic.
- The project aims for a clean, linear history on `main`.

## Pull Requests

1. Fork + branch from `main`.
2. Make your change + tests + update docs/CHANGELOG if user-facing.
3. Ensure all quality commands above are green.
4. Open a PR with a clear description (what, why, how to test).
5. Be patient — as a solo-maintained project, reviews may take time.

Even if you don't send a full PR, high-quality issues and ideas are greatly appreciated.

## Reporting Issues

Please include:
- `grok-utils --version`
- OS + Python version
- Exact command that failed + full traceback
- (If possible) a minimal reproduction using `--grok-home /tmp/fake`

## Philosophy Reminder

- Safe by default (dry-run for anything destructive).
- Beautiful, fast, scriptable output.
- Works against real user `~/.grok` data — no heavy mocks in production code.
- Minimal dependencies.

Thanks for helping make Grok Build even more productive!

— Cobus Greyling
