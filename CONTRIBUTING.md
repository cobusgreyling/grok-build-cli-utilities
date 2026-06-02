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
make lint
make typecheck
make cov
# or: make test
```

See the Makefile for the full list of convenient targets. The GitHub Actions CI runs equivalent checks.

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

## Releasing (maintainers)

1. Update `CHANGELOG.md` under `[Unreleased]` (move to a new dated section when cutting).
2. Bump version in:
   - `pyproject.toml`
   - `src/grok_build_cli_utilities/__init__.py`
3. `git tag -a vX.Y.Z -m "Release vX.Y.Z"` (follow semver).
4. `git push origin main --tags`
5. The `release.yml` workflow will build and publish to PyPI via trusted publishing (configure OIDC on PyPI project settings for this repo + "publish" environment recommended).
6. After publish, verify `pip install grok-build-cli-utilities==X.Y.Z` and update any docs/badges.

Test first with TestPyPI by temporarily editing the release workflow `repository-url`.

Thanks for helping make Grok Build even more productive!

— Cobus Greyling
