# backup

Industrial-strength backup and restore with manifests, selective session inclusion, and safe-by-default restores.

```bash
grok-utils backup --help
```

## create

Create a timestamped, manifest-backed archive of your Grok state.

```bash
grok-utils backup create
grok-utils backup create -o ~/backups/grok-$(date +%F).tar.gz
grok-utils backup create --include-sessions --projects "acme,personal"
```

**Options**

- `-o` / `--output` — Custom output path (defaults to `~/grok-backups/backup-YYYYMMDD-HHMMSS.tar.gz`)
- `--include-sessions` — Include ALL session data (can be huge — use with `--projects` filter)
- `--projects` — Comma-separated project substrings (only relevant with `--include-sessions`)
- `--compress` / `--no-compress`

A `MANIFEST.json` with SHA-256 hashes of every included file is always written inside the archive.

Core state is always included: config, skills, user-settings, memory, plugins, hooks, etc.

## list

List backups found in the conventional `~/grok-backups` directory.

```bash
grok-utils backup list
```

## restore

Restore from a backup archive (defaults to `--dry-run` for safety).

```bash
grok-utils backup restore ~/grok-backups/backup-....tar.gz --dry-run
grok-utils backup restore ... --no-dry-run --force
```

You will normally be prompted for confirmation. Use `--yes` in scripts after careful review.

**Warning**: Restoring will overwrite files in your Grok home. Always start with a dry-run and consider taking a fresh backup first.
