# skills

Full skill lifecycle management: discovery (with correct priority), high-quality scaffolding, validation, pack/unpack for sharing.

```bash
grok-utils skills --help
```

## list

List discovered skills (deduped by priority order).

```bash
grok-utils skills list
grok-utils skills list --all          # include lower-priority / Claude/Cursor compat locations
grok-utils skills list --json
```

## info

Show full details + validation status for a specific skill.

```bash
grok-utils skills info deploy
```

## create

Scaffold a new high-quality `SKILL.md` with proper frontmatter and structure.

```bash
grok-utils skills create deploy --desc "Deploy services following our golden path"
grok-utils skills create my-tool -d "..." --user --force
```

**Arguments & Options**

- `NAME` (required) — Skill name (slug)
- `--desc` / `-d` (required) — One-line description used for invocation
- `--local` / `--user` — Create under `./.grok/skills` (default) or `~/.grok/skills`
- `--force` — Overwrite if the skill already exists

## validate

Validate one or all skills. Exits non-zero if any errors are found.

```bash
grok-utils skills validate
grok-utils skills validate ./my-skill
grok-utils skills validate my-skill --json
```

Checks required fields, length, structure, etc.

## pack / unpack

Package a skill directory into a portable `.tar.gz` (for sharing, backup, version control) and the reverse.

```bash
grok-utils skills pack my-skill -o my-skill.skill.tar.gz
grok-utils skills unpack my-skill.skill.tar.gz --dest ~/.grok/skills
```

See also the sample in `examples/sample-skill/`.
