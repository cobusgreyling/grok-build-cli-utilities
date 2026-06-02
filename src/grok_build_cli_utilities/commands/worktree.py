"""grok-utils worktree - worktree hygiene for Grok users who love isolation."""

from __future__ import annotations

import subprocess
from pathlib import Path

import typer

from ..utils.common import (
    console,
    error,
    get_grok_home,
    iter_sessions,
    make_table,
    success,
)

app = typer.Typer(help="Worktree + Grok session correlation and cleanup", no_args_is_help=True)


@app.command("list")
def list_worktrees(ctx: typer.Context) -> None:
    """List git worktrees in current repo + any associated Grok sessions."""
    try:
        out = subprocess.check_output(
            ["git", "worktree", "list", "--porcelain"], text=True, stderr=subprocess.DEVNULL
        )
    except Exception:
        error("Not in a git repo or git worktree list failed")
        raise typer.Exit(1)

    grok_home = get_grok_home(ctx.obj.get("grok_home") if ctx.obj else None)
    sessions = list(iter_sessions(grok_home))

    # very rough: match session cwds that look like worktrees under this repo
    repo_root = None
    try:
        repo_root = subprocess.check_output(
            ["git", "rev-parse", "--show-toplevel"], text=True
        ).strip()
    except Exception:
        pass

    wt_lines = [line for line in out.splitlines() if line.startswith("worktree ")]
    t = make_table("Git Worktrees + Grok Activity", ["Path", "Grok Sessions", "Last Grok Use"])

    for line in wt_lines:
        wt_path = line.split(" ", 1)[1]
        matching = [s for s in sessions if s.cwd.startswith(wt_path) or wt_path.startswith(s.cwd)]
        lasts = [s.last_active_at for s in matching if s.last_active_at]
        last = max(lasts) if lasts else None
        t.add_row(
            wt_path,
            str(len(matching)),
            str(last)[:19] if last else "—",
        )
    console.print(t)

    if repo_root:
        console.print(f"\n[dim]Repo root: {repo_root}[/dim]")


@app.command("prune-orphaned")
def prune_orphaned(
    ctx: typer.Context,
    dry_run: bool = typer.Option(True, "--dry-run/--no-dry-run"),
    yes: bool = typer.Option(False, "--yes", "-y"),
) -> None:
    """Find sessions whose CWD no longer exists on disk and offer to delete them."""
    grok_home = get_grok_home(ctx.obj.get("grok_home") if ctx.obj else None)
    sessions = list(iter_sessions(grok_home))

    orphans = []
    for s in sessions:
        p = Path(s.cwd)
        if not p.exists():
            orphans.append(s)

    if not orphans:
        success("No orphaned sessions (all session CWDs still exist).")
        return

    console.print(f"Found {len(orphans)} sessions pointing at deleted directories:")
    for o in orphans[:10]:
        console.print(f"  {o.id[:8]}  {o.cwd}")
    if len(orphans) > 10:
        console.print(f"  + {len(orphans) - 10} more")

    if dry_run:
        console.print("[yellow]DRY RUN[/yellow] — nothing deleted. Use --no-dry-run to remove.")
        return

    if not yes and not typer.confirm(f"Delete {len(orphans)} session records?", default=False):
        error("Aborted")
        raise typer.Exit(1)

    import shutil

    count = 0
    for o in orphans:
        try:
            shutil.rmtree(o.path, ignore_errors=True)
            count += 1
        except Exception:
            pass
    success(f"Removed {count} orphaned session directories.")


@app.command("stats")
def worktree_stats(ctx: typer.Context) -> None:
    """Aggregate session stats per worktree-ish directory."""
    grok_home = get_grok_home(ctx.obj.get("grok_home") if ctx.obj else None)
    sessions = list(iter_sessions(grok_home))

    # group by "top level project dir" heuristically
    from collections import defaultdict

    buckets: defaultdict[str, list] = defaultdict(list)
    for s in sessions:
        key = s.cwd
        # if inside a worktree, collapse to parent? simple for now
        buckets[key].append(s)

    t = make_table("Session Activity by CWD", ["CWD", "# Sessions", "Total Msgs", "Most Recent"])
    for cwd, ss in sorted(buckets.items(), key=lambda kv: -len(kv[1]))[:15]:
        actives = [s.last_active_at or s.created_at for s in ss if s.last_active_at or s.created_at]
        recent = max(actives) if actives else None
        t.add_row(
            cwd[:50],
            str(len(ss)),
            str(sum(s.num_messages for s in ss)),
            str(recent)[:10] if recent else "",
        )
    console.print(t)
