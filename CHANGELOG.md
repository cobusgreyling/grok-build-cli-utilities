# Changelog

All notable changes to grok-build-cli-utilities will be documented in this file.

## [Unreleased]

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.0] - 2026-06-03


### Added
- Top-level `grok-utils doctor` command: environment checks for Grok home, sessions/skills/MCP counts, grok binary presence, writability, backups dir, memory, with `--json` support.
- `Makefile` with convenient targets: `make lint`, `make cov`, `make build`, `make clean`, `make pre-commit`, `make dev-install` etc. (updates to README + CONTRIBUTING).
- GitHub release workflow (`.github/workflows/release.yml`) using pypa trusted publishing for PyPI on `v*` tags.
- `SECURITY.md` documenting safe-by-default design, tar protections, and reporting process.
- `parse_age_delta()` shared helper in `utils/common.py` (supports d/w/mo/y/h + bare days; used by prune, with tests).
- Expanded test coverage (JSON paths, prune execute, age delta parser, doctor).
- Issue/PR templates and pull request template for better contributions.
- macOS to CI test matrix (ubuntu + macos x py 3.10-3.12).

### Changed
- Version bumped to 0.3.0.
- Reduced some bare `except Exception` to more specific exceptions in core utils (iter_sessions, load updates, parsers).
- Updated pre-commit, packaging, metadata, and docs as part of the 5 improvement sets.
- `mcp list` delegation is now conditional.
- README intro and install instructions cleaned up (promote published + pipx).
- mcp subcommand help text updated (doctor is now top-level).

### Fixed
- Import/registration for new doctor command.
- Makefile robustness across python/python3 and PATH differences.
- Minor test and help text updates for new features.

[0.3.0]: https://github.com/cobusgreyling/grok-build-cli-utilities/compare/0.2.0...v0.3.0

## [0.2.0] - 2026-06-02

### Added
- Full GitHub Actions CI (`.github/workflows/ci.yml`): matrix on Python 3.10/3.11/3.12, ruff lint + format check, mypy, pytest with coverage.
- Significantly expanded test suite (`tests/test_common.py`, `tests/test_cli.py`): fake session/skill FS fixtures, `iter_sessions`, `safe_extract_tar` (happy + security cases), CLI subcommand tests using `--grok-home` overrides and `CliRunner`.
- `safe_extract_tar()` helper with path traversal protection (uses `filter="data"` on py>=3.12, explicit checks on older versions).
- Post-restore manifest SHA-256 verification in `backup restore` (reports verified count or mismatches).
- `CHANGELOG.md`, `CONTRIBUTING.md`, `.pre-commit-config.yaml`, `.github/dependabot.yml`, `.editorconfig`.
- Version bumped to 0.2.0.

### Changed
- All command modules now import required UI helpers (`Panel`, `info`, `make_table`) from common or rich — no more runtime `NameError`.
- Fixed name shadowing of `info` helper inside the `sessions info` command (now aliased as `ui_info`).
- Improved datetime handling and list comprehensions for mypy cleanliness across `usage`, `sessions`, `worktree`.
- Refactored naive TOML fallback parser in `mcp` for type safety.
- Ran comprehensive `ruff check --fix` + `ruff format .` (removed unused imports, fixed E741, F541, etc.).
- `backup` and `skills` now use the new safe tar extractor for restore/unpack.
- README updated with development quality commands, contributing link, and softened contribution note.
- Test coverage substantially increased (smoke → real logic paths for parsers, common utils, commands).

### Fixed
- Multiple runtime crashes in `sessions`, `backup`, `skills`, `memory` (missing `Panel` / `make_table` / `info`).
- Mypy errors for `max`/`min` over `datetime | None`, repo root path construction, tarfile overloads, bytes/str handling.
- Unsafe tar extraction (zip slip risk) in backup restore and skills unpack.
- Manifest hashes were generated but never verified on restore.

### Security
- Tar extraction now explicitly rejects members that attempt path traversal or escape the target directory.

## [0.1.0] - 2026-05 (initial)

- Initial public release with 7 utilities: sessions, skills, backup, usage, mcp, worktree, memory.
- Safe-by-default operations, rich tables + progress, --json support, real ~/.grok integration.
- Basic smoke tests and pyproject setup.

[0.3.0]: https://github.com/cobusgreyling/grok-build-cli-utilities/compare/0.2.0...v0.3.0
[0.2.0]: https://github.com/cobusgreyling/grok-build-cli-utilities/compare/0.1.0...v0.2.0
