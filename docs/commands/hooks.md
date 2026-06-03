# hooks

Hooks listing, scaffolding and validation.

```bash
grok-utils hooks --help
```

## list

List hooks by event type across user, project and plugin locations.

```bash
grok-utils hooks list
grok-utils hooks list --event SessionStart
grok-utils hooks list --json
```

## create

Scaffold a starter `hooks.json` (or appropriate file) for the given event.

```bash
grok-utils hooks create PostToolUse my-audit
grok-utils hooks create SessionStart audit-start --force
```

## validate

Basic structural validation of hooks files.

```bash
grok-utils hooks validate
```

## doctor

Quick health summary for hooks (count + locations).

```bash
grok-utils hooks doctor
```
