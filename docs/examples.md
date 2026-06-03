# Examples & Tips

Real terminal output is the best experience (`grok-utils usage report`, `sessions list`, `doctor`, etc.). The screenshots below are illustrative.

## Common one-liners

```bash
# Daily standup view
grok-utils usage report --by project --top 5 && grok-utils sessions list -l 5

# Find expensive recent work
grok-utils usage cost --by project --since 2026-05-20

# Clean up after deleting a worktree
cd /path/to/parent/repo
grok-utils worktree prune-orphaned --dry-run
grok-utils worktree prune-orphaned --no-dry-run --yes

# Quick health after an upgrade
grok-utils doctor

# Export last session for a PR description
grok-utils sessions resume --json | jq -r .id | xargs -I{} grok-utils sessions export {} -f md -o last-session.md
```

## Working with JSON everywhere

```bash
grok-utils sessions list --limit 5 --json | jq '.[0].id'
grok-utils usage report --by model --json | jq '.[] | {model, sessions, messages}'
```

## Selective session backups (huge win)

```bash
grok-utils backup create --include-sessions --projects "customer-x,acme"
```

Only sessions whose CWD contains one of the substrings are included — keeps backups manageable.

## Skill development loop

```bash
grok-utils skills create my-review --desc "Code review checklist and patterns"
# edit the generated SKILL.md
grok-utils skills validate my-review
grok-utils skills pack my-review
```

## Using a secondary Grok installation (e.g. for testing)

```bash
grok-utils -g ~/.grok-test doctor
GROK_HOME=~/.grok-test grok-utils usage report
```

## Contributing a new utility idea

See the [Roadmap in the main README](https://github.com/cobusgreyling/grok-build-cli-utilities#roadmap-ideas) and open a well-scoped issue.

Also see [Development](development.md) and the full [CONTRIBUTING.md](https://github.com/cobusgreyling/grok-build-cli-utilities/blob/main/CONTRIBUTING.md) in the repo.
