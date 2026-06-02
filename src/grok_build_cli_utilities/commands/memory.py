"""grok-utils memory - explorer and curator for cross-session memory (even when experimental)."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer

from ..utils.common import (
    console,
    error,
    get_grok_home,
    info,
    make_table,
    success,
    warn,
)

app = typer.Typer(help="Inspect, search and curate Grok's cross-session memory", no_args_is_help=True)


def _memory_root(grok_home: Path) -> Path:
    return grok_home / "memory"


@app.command("list")
def list_memory(ctx: typer.Context) -> None:
    """Show memory files that exist on disk."""
    grok_home = get_grok_home(ctx.obj.get("grok_home") if ctx.obj else None)
    root = _memory_root(grok_home)
    if not root.exists():
        info("No ~/.grok/memory directory yet (memory is experimental and off by default).")
        info("Enable with: grok --experimental-memory  or set [memory] enabled = true in config")
        return

    files = list(root.rglob("*.md")) + list(root.rglob("*.txt"))
    if not files:
        warn("Memory dir exists but no .md files found.")
        return

    t = make_table("Memory Files", ["Path (relative)", "Size", "Modified"])
    for f in sorted(files, key=lambda p: -p.stat().st_mtime)[:30]:
        rel = f.relative_to(root)
        st = f.stat()
        t.add_row(str(rel), f"{st.st_size} B", str(st.st_mtime)[:10])
    console.print(t)


@app.command("stats")
def memory_stats(ctx: typer.Context) -> None:
    """Basic stats + index info if present."""
    grok_home = get_grok_home(ctx.obj.get("grok_home") if ctx.obj else None)
    root = _memory_root(grok_home)
    if not root.exists():
        info("Memory not initialized.")
        return

    md_files = list(root.rglob("*.md"))
    total_bytes = sum(f.stat().st_size for f in md_files)
    index = root / "index.sqlite"  # may be named differently; grok uses internal
    idx_size = index.stat().st_size if index.exists() else 0

    console.print(Panel.fit(
        f"Memory root: {root}\n"
        f"Markdown files: {len(md_files)}\n"
        f"Total content size: {total_bytes / 1024:.1f} KiB\n"
        f"Index present: {'yes (' + str(idx_size) + ' B)' if idx_size else 'no (or different name)'}",
        title="Memory Stats",
    ))


@app.command("search")
def search_memory(
    ctx: typer.Context,
    query: str = typer.Argument(..., help="Text to search in memory files"),
    limit: int = typer.Option(15, "--limit"),
) -> None:
    """Simple grep across all memory markdown."""
    grok_home = get_grok_home(ctx.obj.get("grok_home") if ctx.obj else None)
    root = _memory_root(grok_home)
    if not root.exists():
        warn("No memory dir.")
        return

    hits = []
    for md in root.rglob("*.md"):
        try:
            txt = md.read_text(encoding="utf-8", errors="ignore")
            if query.lower() in txt.lower():
                # grab a snippet
                idx = txt.lower().find(query.lower())
                snip = txt[max(0, idx - 30): idx + 80].replace("\n", " ")
                hits.append((md.relative_to(root), snip))
                if len(hits) >= limit:
                    break
        except Exception:
            continue

    if not hits:
        warn(f"No hits for '{query}' in memory files.")
        return

    t = make_table(f"Memory matches: {query}", ["File", "Snippet"])
    for path, snip in hits:
        t.add_row(str(path), snip[:90])
    console.print(t)


@app.command("paths")
def memory_paths(ctx: typer.Context) -> None:
    """Print the canonical memory file paths (handy for $EDITOR)."""
    grok_home = get_grok_home(ctx.obj.get("grok_home") if ctx.obj else None)
    root = _memory_root(grok_home)
    console.print("Global:     ", root / "MEMORY.md")
    console.print("Workspace:  ", root / "<project-slug>-<hash>/MEMORY.md")
    console.print("Sessions:   ", root / "<project-slug>-<hash>/sessions/")
    console.print("\nUse [bold]grok memory edit[/bold] (built-in) or your $EDITOR on the paths above.")
