"""grok-utils backup - first class backup and restore for Grok Build state."""

from __future__ import annotations

import hashlib
import json
import tarfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import typer
from rich.progress import Progress

from ..utils.common import (
    console,
    error,
    get_grok_home,
    get_sessions_dir,
    info,
    make_table,
    Panel,
    safe_extract_tar,
    success,
    warn,
)

app = typer.Typer(help="Backup and restore your Grok Build world safely", no_args_is_help=True)


MANIFEST_NAME = "grok-backup-manifest.json"


def _hash_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _gather_paths(
    grok_home: Path, include_sessions: bool, project_filter: Optional[str]
) -> list[tuple[Path, Path]]:
    """Return (src_abs, arcname_rel) pairs."""
    items: list[tuple[Path, Path]] = []

    # core config & state (always)
    for name in [
        "config.toml",
        "user-settings.json",
        "settings.json",
        "auth.json",
        "models_cache.json",
        "CHANGELOG.md",
        "version.json",
    ]:
        p = grok_home / name
        if p.exists():
            items.append((p, Path(name)))

    # skills (user)
    skills = grok_home / "skills"
    if skills.exists():
        for p in skills.rglob("*"):
            if p.is_file():
                items.append((p, p.relative_to(grok_home)))

    # mcp? from config, but also any local
    # plugins
    plugins = grok_home / "plugins"
    if plugins.exists():
        for p in plugins.rglob("*"):
            if p.is_file():
                items.append((p, p.relative_to(grok_home)))

    # memory (if present)
    mem = grok_home / "memory"
    if mem.exists():
        for p in mem.rglob("*"):
            if p.is_file():
                items.append((p, p.relative_to(grok_home)))

    # sessions (selective)
    if include_sessions:
        sess_root = get_sessions_dir(grok_home)
        if sess_root.exists():
            for p in sess_root.rglob("*"):
                if p.is_file():
                    rel = p.relative_to(grok_home)
                    if project_filter and project_filter.lower() not in str(rel).lower():
                        continue
                    items.append((p, rel))

    return items


@app.command("create")
def create_backup(
    ctx: typer.Context,
    output: Optional[Path] = typer.Option(
        None,
        "--output",
        "-o",
        help="Output path (default: ~/grok-backups/backup-YYYYMMDD-HHMMSS.tar.gz)",
    ),
    include_sessions: bool = typer.Option(
        False, "--include-sessions", help="Include ALL session data (can be huge)"
    ),
    projects: Optional[str] = typer.Option(
        None, "--projects", help="Comma separated project substrings (with --include-sessions)"
    ),
    compress: bool = typer.Option(True, "--compress/--no-compress"),
) -> None:
    """Create a timestamped, manifest-backed archive of your Grok state."""
    grok_home = get_grok_home(ctx.obj.get("grok_home") if ctx.obj else None)

    if not grok_home.exists():
        error(f"No Grok home at {grok_home}")
        raise typer.Exit(1)

    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    default_dir = Path.home() / "grok-backups"
    default_dir.mkdir(parents=True, exist_ok=True)
    out_path = output or (default_dir / f"grok-backup-{ts}.tar.gz")

    project_filter = None
    if projects:
        project_filter = projects  # simple contains check later

    items = _gather_paths(grok_home, include_sessions, project_filter)
    if not items:
        warn("Nothing to back up.")
        return

    mode = "w:gz" if compress else "w"
    manifest: dict = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "grok_home": str(grok_home),
        "include_sessions": include_sessions,
        "projects_filter": projects,
        "files": [],
        "version": "1",
    }

    with tarfile.open(out_path, mode) as tar, Progress() as prog:  # type: ignore[call-overload]
        task = prog.add_task("Backing up...", total=len(items))
        for src, arc in items:
            try:
                tar.add(src, arcname=str(arc))
                h = _hash_file(src) if src.is_file() else ""
                manifest["files"].append(
                    {
                        "path": str(arc),
                        "size": src.stat().st_size if src.exists() else 0,
                        "sha256": h,
                    }
                )
            except Exception as e:
                warn(f"Skipped {src}: {e}")
            prog.advance(task)

    # write manifest inside archive too + sidecar
    mf_path = out_path.with_suffix(out_path.suffix + ".manifest.json")
    mf_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    # append manifest to tar as well
    with tarfile.open(out_path, "a:gz" if compress else "a") as tar:  # type: ignore[call-overload]
        tar.add(mf_path, arcname=MANIFEST_NAME)

    success(f"Backup created: {out_path}")
    console.print(f"Manifest: {mf_path}")
    console.print(f"Files archived: {len(manifest['files'])}")


@app.command("restore")
def restore_backup(
    ctx: typer.Context,
    archive: Path = typer.Argument(..., exists=True, help="Path to grok-backup-*.tar.gz"),
    dry_run: bool = typer.Option(
        True, "--dry-run/--no-dry-run", help="Show plan only (safe default)"
    ),
    force: bool = typer.Option(False, "--force", help="Overwrite existing files without asking"),
    target: Optional[Path] = typer.Option(
        None, "--target", help="Restore into different Grok home (advanced)"
    ),
) -> None:
    """Restore from backup (defaults to dry-run for safety)."""
    grok_home = target or get_grok_home(ctx.obj.get("grok_home") if ctx.obj else None)

    if not archive.exists():
        error("Archive not found")
        raise typer.Exit(1)

    manifest = None
    try:
        with tarfile.open(archive, "r:*") as tar:  # type: ignore[call-overload]
            if MANIFEST_NAME in tar.getnames():
                mf = tar.extractfile(MANIFEST_NAME)
                if mf:
                    manifest = json.loads(mf.read().decode())
    except (tarfile.TarError, OSError, json.JSONDecodeError, UnicodeDecodeError, ValueError):
        pass

    if manifest:
        console.print(
            Panel.fit(
                f"Backup from: {manifest.get('created_at')}\n"
                f"Original home: {manifest.get('grok_home')}\n"
                f"Files: {len(manifest.get('files', []))}\n"
                f"Sessions included: {manifest.get('include_sessions')}",
                title="Backup Manifest",
            )
        )

    if dry_run:
        console.print("[bold yellow]DRY-RUN[/bold yellow] — would extract into", grok_home)
        with tarfile.open(archive, "r:*") as tar:  # type: ignore[call-overload]
            for m in tar.getmembers()[:12]:
                if m.name == MANIFEST_NAME:
                    continue
                console.print(f"  {m.name}")
            if len(tar.getmembers()) > 13:
                console.print(f"  ... +{len(tar.getmembers()) - 13} more")
        console.print("Re-run with [bold]--no-dry-run[/bold] to perform restore.")
        return

    if not force and not typer.confirm(
        f"Restore will write into {grok_home}. Continue?", default=False
    ):
        error("Aborted")
        raise typer.Exit(1)

    grok_home.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive, "r:*") as tar:  # type: ignore[call-overload]
        # filter out manifest
        members = [m for m in tar.getmembers() if m.name != MANIFEST_NAME]
        safe_extract_tar(tar, grok_home, members=members)

    success(f"Restored into {grok_home}")

    # Verify hashes from manifest if present (P0 safety improvement)
    if manifest and manifest.get("files"):
        verified = 0
        mismatches = 0
        for entry in manifest["files"]:
            p = grok_home / entry.get("path", "")
            expected = entry.get("sha256", "")
            if expected and p.exists() and p.is_file():
                if _hash_file(p) == expected:
                    verified += 1
                else:
                    mismatches += 1
                    warn(f"Hash mismatch after restore: {entry['path']}")
        if mismatches == 0 and verified > 0:
            success(f"Verified {verified} file hash(es) from manifest.")
        elif mismatches > 0:
            warn(f"{mismatches} hash mismatch(es) detected after restore!")

    warn("You may need to restart any running Grok sessions or re-login.")


@app.command("list")
def list_backups(
    ctx: typer.Context,
) -> None:
    """List backups in the conventional ~/grok-backups location."""
    bdir = Path.home() / "grok-backups"
    if not bdir.exists():
        info("No ~/grok-backups directory yet.")
        return

    t = make_table("Available Backups", ["File", "Size", "Created"])
    for p in sorted(bdir.glob("grok-backup-*.tar.gz"), reverse=True):
        st = p.stat()
        created = datetime.fromtimestamp(st.st_mtime, tz=timezone.utc).strftime("%Y-%m-%d %H:%M")
        size = f"{st.st_size / 1_048_576:.1f} MiB"
        t.add_row(p.name, size, created)
    console.print(t)
