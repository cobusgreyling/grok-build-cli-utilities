## Summary
<!-- One paragraph: what + why -->

## Changes
- 
- 

## Testing
- [ ] `ruff check . && ruff format --check .`
- [ ] `mypy src/grok_build_cli_utilities --ignore-missing-imports`
- [ ] `pytest -q --cov=src/grok_build_cli_utilities --cov-report=term-missing`
- [ ] Manual test with real `~/.grok` (or `--grok-home`) + `--dry-run` paths
- [ ] Added/updated tests for new behavior

## Screenshots / Output (if UI change)
<!-- Paste rich terminal output or before/after -->

## Checklist
- [ ] CHANGELOG.md updated (under Unreleased) for user-facing changes
- [ ] Docs / README updated if needed
- [ ] No new bare `except Exception` without good reason
- [ ] Dry-run + confirmation preserved for destructive ops

Fixes # (if any)
