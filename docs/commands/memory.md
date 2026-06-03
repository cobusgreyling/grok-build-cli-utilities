# memory

Cross-session memory explorer and curator (experimental — works the moment you enable memory in Grok).

```bash
grok-utils memory --help
```

## list

Show memory files that exist on disk.

```bash
grok-utils memory list
```

## stats

Basic stats + index information if present.

```bash
grok-utils memory stats
```

## search

Simple grep across all memory markdown files.

```bash
grok-utils memory search "architecture decision"
grok-utils memory search "TODO" --json
```

## paths

Print the canonical memory file paths (handy for `$EDITOR` or scripting).

```bash
grok-utils memory paths
```
