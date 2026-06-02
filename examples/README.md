# Examples

This directory contains example outputs, sample skill packs, and configuration snippets.

## Running after install

```bash
pip install -e .
grok-utils --help
grok-utils sessions list --limit 5
grok-utils usage report --by model
```

## Sample skill pack

See the `test-skill.skill.tar.gz` (if present) or generate one:

```bash
grok-utils skills create demo-skill --desc "Example skill created by grok-utils"
grok-utils skills pack demo-skill -o examples/demo-skill.skill.tar.gz
```

## Backup example

```bash
grok-utils backup create --include-sessions --projects my-project
```

All utilities are designed to be safe by default (dry-run where destructive).
