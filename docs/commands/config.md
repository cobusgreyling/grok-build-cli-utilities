# config

Inspect `config.toml`, key paths, settings and light validation.

```bash
grok-utils config --help
```

## show

Pretty-print `config.toml` (and a few other key settings files).

```bash
grok-utils config show
```

## get

Get a single (dotted) value from the loaded config.

```bash
grok-utils config get model
grok-utils config get mcp_servers
```

## paths

Show important Grok directories and files (very handy for scripting and `$EDITOR`).

```bash
grok-utils config paths
```

Typical paths include:

- Grok home
- Config file
- Sessions dir
- Skills dirs (various scopes)
- Logs, memory, plugins, hooks, etc.

## validate

Light structural validation / sanity checks on config.

```bash
grok-utils config validate
grok-utils config validate --json
```
