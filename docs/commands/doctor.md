# doctor

Diagnose your Grok Build environment and grok-utils setup.

```bash
grok-utils doctor
grok-utils doctor --json
grok-utils -g /tmp/other-grok doctor
```

## What it checks

- Python version and platform
- grok-utils version
- Grok home existence + writability
- Sessions directory and count
- Skills discovered (across all priority locations)
- Configured MCP servers
- Plugins and hooks counts (user + project)
- Grok CLI binary presence (`~/.grok/bin/grok`)
- Conventional backups directory (`~/grok-backups`)
- Memory directory (experimental)

## Output

By default a pretty Rich table is printed plus a summary line.

With `--json` you get machine-readable output suitable for CI or scripting.

## Tips

- Run this after installing/upgrading Grok Build or grok-utils.
- Use it in scripts with `--json` and `jq` to gate other operations.
- Many commands remain useful even if some checks are in "⚠" state.
