# worktree

Git worktree + Grok session hygiene tools. Especially valuable if you use `git worktree` heavily and spin up many parallel Grok sessions.

```bash
grok-utils worktree --help
```

## list

List git worktrees in the current repo together with any associated Grok sessions (matched by CWD).

```bash
grok-utils worktree list
```

## stats

Aggregate session stats (count, messages, last activity) per worktree-ish directory.

```bash
grok-utils worktree stats
```

## prune-orphaned

Find sessions whose CWD no longer exists on disk ("zombie" sessions) and offer to delete the session records.

```bash
grok-utils worktree prune-orphaned --dry-run
grok-utils worktree prune-orphaned --no-dry-run --yes
```

This is safe-by-default and extremely useful for cleaning up after deleting worktrees.
