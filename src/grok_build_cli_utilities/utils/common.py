"""Shared utilities for grok-utils: paths, discovery, rich UI helpers, scanning."""

from __future__ import annotations

import json
import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Optional

import typer
from dateutil import parser as date_parser
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress
from rich.table import Table

console = Console()

# Default Grok home
DEFAULT_GROK_HOME = Path.home() / ".grok"


def get_grok_home(custom: Optional[Path] = None) -> Path:
    """Discover Grok home directory.

    Priority:
    1. Explicit --grok-home flag
    2. GROK_HOME env var
    3. ~/.grok (default)
    """
    if custom:
        return custom.expanduser().resolve()
    env = os.environ.get("GROK_HOME")
    if env:
        return Path(env).expanduser().resolve()
    return DEFAULT_GROK_HOME


def get_sessions_dir(grok_home: Path) -> Path:
    return grok_home / "sessions"


def get_skills_dirs(grok_home: Path) -> list[tuple[str, Path]]:
    """Return (scope, path) for skill discovery locations in priority order."""
    repo_root = find_repo_root()
    return [
        ("local", Path.cwd() / ".grok" / "skills"),
        ("repo", repo_root / ".grok" / "skills" if repo_root else Path()),
        ("user", grok_home / "skills"),
        ("claude", Path.home() / ".claude" / "skills"),
        ("cursor", Path.home() / ".cursor" / "skills"),
    ]


def find_repo_root(start: Optional[Path] = None) -> Optional[Path]:
    """Walk up to find .git directory."""
    p = (start or Path.cwd()).resolve()
    for parent in [p] + list(p.parents):
        if (parent / ".git").exists():
            return parent
    return None


def parse_timestamp(ts: Any) -> Optional[datetime]:
    """Parse various timestamp formats to aware datetime."""
    if ts is None:
        return None
    if isinstance(ts, (int, float)):
        # unix seconds or millis
        if ts > 1e12:
            ts = ts / 1000.0
        return datetime.fromtimestamp(ts, tz=timezone.utc)
    if isinstance(ts, str):
        try:
            dt = date_parser.isoparse(ts)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except Exception:
            pass
    return None


@dataclass
class SessionSummary:
    """Parsed session summary.json + derived info."""

    id: str
    cwd: str
    created_at: Optional[datetime]
    updated_at: Optional[datetime]
    last_active_at: Optional[datetime]
    num_messages: int
    num_chat_messages: int
    current_model_id: str
    agent_name: str
    path: Path
    summary_text: str = ""


def iter_sessions(grok_home: Path, progress: Optional[Progress] = None) -> Iterator[SessionSummary]:
    """Yield all sessions by walking summaries. Fast path using summary.json."""
    sessions_root = get_sessions_dir(grok_home)
    if not sessions_root.exists():
        return

    dirs = list(sessions_root.rglob("*/summary.json"))
    task = None
    if progress:
        task = progress.add_task("Scanning sessions...", total=len(dirs))

    for sfile in dirs:
        try:
            with open(sfile) as f:
                data = json.load(f)
            info = data.get("info", {})
            sid = info.get("id") or sfile.parent.name
            cwd = info.get("cwd", str(sfile.parent.parent))
            created = parse_timestamp(data.get("created_at"))
            updated = parse_timestamp(data.get("updated_at"))
            last = parse_timestamp(data.get("last_active_at"))
            yield SessionSummary(
                id=sid,
                cwd=cwd,
                created_at=created,
                updated_at=updated,
                last_active_at=last,
                num_messages=data.get("num_messages", 0),
                num_chat_messages=data.get("num_chat_messages", 0),
                current_model_id=data.get("current_model_id", "unknown"),
                agent_name=data.get("agent_name", ""),
                path=sfile.parent,
                summary_text=data.get("session_summary", ""),
            )
        except Exception:
            # Skip corrupt
            pass
        finally:
            if progress and task is not None:
                progress.advance(task)


def load_session_updates(session_path: Path, limit: int = 1000) -> list[dict]:
    """Load recent updates.jsonl for deeper analysis (tool counts etc)."""
    upd = session_path / "updates.jsonl"
    if not upd.exists():
        return []
    out: list[dict] = []
    try:
        with open(upd) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                out.append(json.loads(line))
                if len(out) >= limit:
                    break
    except Exception:
        pass
    return out


def count_tool_calls(updates: list[dict]) -> dict[str, int]:
    """Rough tool call stats from updates stream."""
    counts: dict[str, int] = {}
    for u in updates:
        upd = u.get("params", {}).get("update", {})
        if upd.get("sessionUpdate") == "tool_call":
            title = upd.get("title", "unknown")
            counts[title] = counts.get(title, 0) + 1
        # also check tool_call_update completed etc.
        if "toolCall" in str(upd):
            # fallback
            pass
    return counts


def format_dt(dt: Optional[datetime]) -> str:
    if not dt:
        return "—"
    return dt.astimezone().strftime("%Y-%m-%d %H:%M")


def format_age(dt: Optional[datetime]) -> str:
    if not dt:
        return "—"
    delta = datetime.now(timezone.utc) - dt
    days = delta.days
    if days > 30:
        return f"{days // 30}mo ago"
    if days > 0:
        return f"{days}d ago"
    hrs = delta.seconds // 3600
    if hrs > 0:
        return f"{hrs}h ago"
    mins = (delta.seconds // 60) % 60
    return f"{mins}m ago"


def make_table(title: str, columns: list[str]) -> Table:
    t = Table(title=title, show_header=True, header_style="bold cyan", box=None, padding=(0, 1))
    for c in columns:
        t.add_column(c)
    return t


def success(msg: str) -> None:
    console.print(f"[green]✓[/green] {msg}")


def warn(msg: str) -> None:
    console.print(f"[yellow]⚠[/yellow] {msg}")


def error(msg: str) -> None:
    console.print(f"[red]✗[/red] {msg}")


def info(msg: str) -> None:
    console.print(f"[blue]ℹ[/blue] {msg}")


def print_panel(title: str, content: str, style: str = "cyan") -> None:
    console.print(Panel(content, title=title, border_style=style))


def confirm_or_exit(prompt: str = "Are you sure?") -> bool:
    return typer.confirm(prompt, default=False)


def get_sqlite_search_db(grok_home: Path) -> Optional[Path]:
    db = get_sessions_dir(grok_home) / "session_search.sqlite"
    return db if db.exists() else None


def search_sessions_sqlite(db_path: Path, query: str, limit: int = 50) -> list[dict]:
    """Use the built-in FTS if available."""
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        # session_docs_fts is the virtual table
        rows = conn.execute(
            "SELECT * FROM session_docs_fts WHERE session_docs_fts MATCH ? LIMIT ?",
            (query, limit),
        ).fetchall()
        return [dict(r) for r in rows]
    except Exception:
        return []
