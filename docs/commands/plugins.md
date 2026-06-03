# plugins

Plugin discovery, inventory and validation for the maturing Grok plugins ecosystem.

```bash
grok-utils plugins --help
```

## list

List discovered plugins with component summary (skills / agents / hooks / MCP).

```bash
grok-utils plugins list
grok-utils plugins list --all   # include marketplace cache sources
grok-utils plugins list --json
```

## info

Show details for one plugin.

```bash
grok-utils plugins info my-plugin
```

## validate

Validate one plugin or all discovered ones.

```bash
grok-utils plugins validate
grok-utils plugins validate my-plugin
```

## inventory

Aggregate view: total skills, agents, hooks, MCP servers across all plugins.

```bash
grok-utils plugins inventory
```
