# Changelog

All notable changes to grok-build-cli-utilities will be documented in this file.

## [Unreleased]

### Added
- **`usage cost` / `usage report --all`**: print every bucket. Default `--top` is 10 by list$ (cost was 8). Truncated tables say `top 10 of 18 · TOTALS is the whole window · --all to see all`. `--all` overrides `--top`. TOTALS is the whole window. Hidden rows stay uncombined.
- **`usage cost --by session`** and **`--by pr`**: `--by session` is one row per chat. `--by pr` is one row per GitHub PR when that chat created exactly one PR (`repo#N`, issue from `Fixes` or `Closes`). Several PRs from one parent chat stay one unsplit row (`widgets #12,15` or mixed `widgets #7,8,14 · notes #15`). A one-line footnote marks unsplit multi-PR rows. No GitHub owner. No session UUID in the key unless two rows share a display Key (`notes#22 · 01a05e3c…`). Unlabeled `--by session` Keys pretty-print `*-issue-N` clones (`notes-issue-9` → `notes#9`) and Grok worktrees. Sessions with no created PR are omitted from `--by pr` unless `--include-unlabeled`. Chat text and `get_pull_request` are ignored. PR-level Keys need github `create_pull_request` or `gh pr create` in `updates.jsonl`, with session cwd in that repo.
- **Weekly pool reset** on `auth status` / cost footer / JSON (`weekly_resets_at`): `currentPeriod.end` from the same billing log line Build `/usage` uses (local clock matches “Resets: August 27, 19:08”). Fallback `billingPeriodEnd`.
- **SuperGrok vs Heavy from billing log** (`ctx.subscriptionTier` on `billing: fetched credits config`). Cost mix/wallet/auth status/`-P` label **Heavy pool** vs SuperGrok; planner footer marks the **current plan** and treats the other subscription row as a what-if. Session `/usage` turns do not store the plan.
- **grok-4.6 list-rate profile** (`-m grok-4.6` / `4.6` / `grok-4.6-build`): $2 / $0.50 / $6 per 1M (≤200k).
- **`grok-utils auth status`**: SuperGrok session vs API key; optional `--history`; **Extra Credits $** + **weekly %** from billing log.
- Auth path + wallet snapshot on `usage cost` footer / JSON (`prepaid_balance_usd`, `weekly_usage_pct`).
- **Path/regime cash scales**: API 1.0, SuperGrok pool 0.0, overage 1.9; weekly% unknown → list$ scale + caveat.
- **`--topoff-discount` 0..1** optional pin for est_cash$; **`-P` always ranks** offered pack promos **−20/−25/−40%** in the plan table (no flag required) + single ★ best plan for the window.
- Plan-advisor accuracy: est$ mix **% sum to 100**; tops **ceil to pack size** (`topoff_pack_usd`, default 100); promo dependency in ★ banner; week list$ pace check; notes separate pool context from $/mo formula.
- Wallet labels (credits **remaining**, weekly limit **% used**); SuperGrok (?) footnote; **`--detail`** gates savings attribution, 1.9× source, hybrid tip, week pace, per-app regime; JSON: `wallet`, `plan_advisor.candidates/best` (Heavy promo rows + `active` pin for `--topoff-discount`), `week_list_usd`, `list_pct`, per-bucket `regime_list_pct`.
- `est_cash$` = est$ × (1 − discount) when promo modeled; primary plan “best fit” stays full price.

### Fixed
- **est$ jumped as `unified.jsonl` grew / truncated**: weekly-timeline compaction moved plateau timestamps forward, so same-week Heavy/SuperGrok pool turns fell *before* the first remaining billing sample and were billed at list$ (`SuperGrok (?)` ×1). Compaction now keeps the earliest timestamp of each weekly-% plateau. Turns before the first sample reuse that sample when it is still in-pool and within 7 days (and label Heavy when the log only ever shows Heavy). First-sample overage still stays unknown @ list$ so historical Extra Credits burn is not zeroed.

### Changed
- **`usage cost --by app`**: repo inferred from cwd. Issue worktrees (`repo-issue-N`) and Grok worktrees (`~/.grok/worktrees/github-…`) roll into one Key per repo. Grouping is case-insensitive. Display prefers the `GitHub/` folder spelling. `#N` is gone from `--by app` for issue clones. `--by pr` still lists every created PR. `--by project` is still the full cwd. Unlabeled `--by session` Keys still pretty-print `repo#N` / `(worktree)` so chats stay distinct.
- **`usage cost` default `--top`** is 10, matching `usage report`. `--top 0` prints no rows (not all rows).
- **`usage --from` / `--to` / `--since`** are inclusive **local** calendar dates by default (same clock as weekly resets / Build `/usage`). Late-evening local work stays on that local day. `--tz UTC` or `--tz America/New_York` (IANA) and `[usage] date_tz` are the escape hatch. `--by day` buckets use the same zone. JSON includes `date_tz`.
- **`make ci`** is the required local gate before a PR (`ruff` pin `>=0.15.0,<0.16`, `ruff check`, `ruff format --check`, mypy, pytest cov). CONTRIBUTING / docs / PR template no longer treat pytest-green as sufficient.
- Pre-commit `ruff-pre-commit` hook pinned to **v0.15.22** so local format matches CI.
- **list$** uses Build **`costUsdTicks ÷ 10^10`** (xAI cost tracking — same $ as `/usage` Session Cost). Pass `-m` to reconstruct from a published rate table instead. Tick conversion was previously ÷1e9 (10× too high).
- **list$ default rate table** (fallback / `-m`) is **grok-4.6** ($2 / $0.50 / $6 per 1M, ≤200k; verified 2026-08-13). Reconstruction does not double-count reasoning already inside `outputTokens`. Pin older 4.5 cache rate with `-m grok-4.5` ($2 / $0.30 / $6). `grok-4.6*` no longer fuzzy-matches grok-4 ($3 / $15).
- Default est$ is path/regime-aware (not a single 0.57 blend). Multi-day blends remain optional via `--cash-scale` / prepaid-fit.
- Top-off discount clamp is **0..1** (was 0..0.95) so free-credit scenarios work.
- **`usage cost` human output simplified**: compact TOTALS / est$ mix / wallet line; plan-advisor collapses duplicate Pure API rows; **`--detail` / `-v`** adds promo table + overage one-liner only (long caveats → `usage info`).
- **`usage report` token path** aligned with cost: auth-mix est$, **Share(list$)**, compact wallet/footer (no empty Share bars when SuperGrok pool scale is 0).
- **Refactor**: shared `build_token_cost_window` for cost + report; one-pass per-key est$; single billing log parse (`load_billing_snapshot`); FAQ moved to `usage_faq.py`; display helpers in `usage_display.py`; legacy report/rough → `usage_legacy.py`.
- **`usage report` default `--by app`** (short names + list$/est$). SuperGrok est$ mix splits pool / overage / unknown regimes.
- **Doctor** Auth path row includes Extra Credits $ + weekly % when billing log has them.

## [0.4.0] - 2026-08-06

### Added
- Token-accurate `usage cost` from `turn_completed.usage` in `updates.jsonl` (input/output/cached/reasoning, deduped by prompt_id).
- Pure-API rate table (`utils/pricing.py`); **`--rates-model` / `-m`** (default **grok-4.5**).
- **list$ + est$** on `usage cost` and token-based `usage report` (`est$` = list$ × cash_scale, default **0.57**).
- Optional `--prepaid-usd` / `--credits-remaining`, `--cash-scale`, toml `[usage] cash_scale`.
- **`--plan-advisor` / `-P`**: pure API vs SuperGrok vs SuperGrok Heavy (run-rate → monthly; soft “if intensity holds”).
- Optional SuperGrok/cash allocation: `--invoice-usd` / `--fixed-usd` by `costUsdTicks`.
- Date span in report/cost titles; warn when `--from`/`--to` extend past session data; JSON `result_from` / `result_to`.
- Novice **FAQ** in `usage info` + `docs/commands/usage.md` (Session Cost vs list$/est$, Credits, Weekly limit, Auto topup).
- Tests: `tests/test_usage_tokens.py`.

### Changed
- **`usage cost` default** uses real turn tokens (not message×400). Legacy: `--mode rough`.
- Help: clear metavars / “Requires amount” for value options; examples for open-ended `--from` and invoice/prepaid.
- Docs: Phase 1 maintain defaults when xAI announces changes; future Models API list-rate refresh notes (not in v1 network path).

## [0.3.1] - 2026-06-03

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

### Added
- Shared `load_toml()` in common (prefers `tomllib` on Python >=3.11, falls back to `tomli`, improved naive with dotted section support). Used by `mcp`, `config`, `doctor`, parsers.
- `safe_read_text()` and `safe_json_load()` helpers in common to reduce duplication and broad excepts.
- `python -m grok_build_cli_utilities` support via `__main__.py`.
- `CODE_OF_CONDUCT.md`.
- More tests exercising analyze/export/resume (json), usage cost, config get, load_toml, signals/rewinds, tail_logs, project rules, plugins/hooks create paths (coverage up ~5-10 pts on parsers/sessions/usage/config).
- CI: concurrency cancel-in-progress, wheel build + twine check verification on every matrix run (ubuntu + macos).
- PyPI badge in README.

### Changed
- `parse_plugin()` now correctly returns `None` for non-plugin directories (was dead `pass` guard) — fixes junk dir pollution in `plugins list`.
- Centralized TOML loading; removed duplicated naive parser code in `parsers.py` and `mcp.py`.
- Reduced bare `except Exception:` from ~35 to ~12 (most remaining are intentional "best effort" fallbacks in load_toml / _safe_* doctor counts / yaml edge). Switched many to specific (JSONDecode, OSError, ValueError, subprocess.* etc).
- Updated version to 0.3.1, test expectations, bug report template placeholder.
- README install section emphasizes `pipx`, added 0.3.1 highlights, doctor in verify, expanded command count note.
- Minor: bug template version, test comments, mypy/ruff clean.

### Fixed
- Plugin discovery would treat arbitrary subdirs under .grok/plugins as valid plugins.
- Inconsistent TOML parsing between mcp/doctor vs config command.
- Potential NameError on json in except clauses in config.py non-json path (now top-level import).

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
