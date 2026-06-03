# mcp

MCP server superpowers: inspection, health checks, lightweight testing and easy example injection.

```bash
grok-utils mcp --help
```

## list

List configured MCP servers from your `config.toml` (works even without `tomli` on Python < 3.11) plus what the Grok CLI itself reports.

```bash
grok-utils mcp list
```

## doctor

Health check MCP servers (config presence + basic reachability hints via PATH checks for stdio servers).

```bash
grok-utils mcp doctor
```

## test

Attempt a very lightweight test of a named server (delegates to `grok mcp ...` when possible).

```bash
grok-utils mcp test my-github-server
```

## add-example

Append a well-known example MCP server config block to your `config.toml`. You must still edit paths, tokens, etc.

```bash
grok-utils mcp add-example myfs --kind filesystem
grok-utils mcp add-example gh --kind github
```

Supported example kinds (at time of writing): `filesystem`, `github`, `sqlite`, and others — the command will list them if you pass an unknown kind.

After adding, restart or reload your Grok session / TUI for the change to take effect.
