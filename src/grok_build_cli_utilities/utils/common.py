"""Shared utilities for grok-utils: paths, discovery, rich UI helpers, scanning."""

from __future__ import annotations

import json
import os
import sqlite3
import sys
import tarfile
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
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


def get_plugin_dirs(grok_home: Path) -> list[tuple[str, Path]]:
    """Return (scope, path) for plugin discovery (user + project/local)."""
    repo_root = find_repo_root()
    return [
        ("local", Path.cwd() / ".grok" / "plugins"),
        ("repo", repo_root / ".grok" / "plugins" if repo_root else Path()),
        ("user", grok_home / "plugins"),
    ]


def get_hooks_dirs(grok_home: Path) -> list[tuple[str, Path]]:
    """Return (scope, path) for hooks discovery."""
    repo_root = find_repo_root()
    return [
        ("local", Path.cwd() / ".grok" / "hooks"),
        ("repo", repo_root / ".grok" / "hooks" if repo_root else Path()),
        ("user", grok_home / "hooks"),
    ]


def get_config_path(grok_home: Path) -> Path:
    return grok_home / "config.toml"


def get_logs_path(grok_home: Path) -> Path:
    return grok_home / "logs" / "unified.jsonl"


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
        except (ValueError, TypeError, OverflowError):
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
        except (json.JSONDecodeError, KeyError, OSError, TypeError):
            # Skip corrupt or unreadable session summary
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
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
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


def parse_age_delta(spec: str) -> timedelta:
    """Parse simple age specs like '30d', '6mo', '1y', '2w' into timedelta.

    Used by prune and similar age-based filters. Falls back to 90 days on parse error.
    """
    spec = spec.strip().lower()
    try:
        if spec.endswith("d"):
            return timedelta(days=int(spec[:-1]))
        if spec.endswith("w"):
            return timedelta(weeks=int(spec[:-1]))
        if spec.endswith("mo"):
            return timedelta(days=int(spec[:-2]) * 30)
        if spec.endswith("y"):
            return timedelta(days=int(spec[:-1]) * 365)
        if spec.endswith("h"):
            return timedelta(hours=int(spec[:-1]))
        # bare number = days
        return timedelta(days=int(spec))
    except (ValueError, TypeError, IndexError):
        # safe default
        return timedelta(days=90)


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
    except (sqlite3.Error, OSError, ValueError, TypeError):
        return []


def safe_extract_tar(
    tar: tarfile.TarFile, target_dir: Path, *, members: list[tarfile.TarInfo] | None = None
) -> None:
    """Safely extract a tar archive, preventing path traversal attacks (zip slip).

    - On Python >= 3.12 uses the built-in 'data' filter.
    - On older versions performs an explicit prefix check before extraction.
    Raises RuntimeError on any attempted traversal.
    Pass members= to extract a filtered subset (e.g. excluding manifest).
    """
    target_dir = target_dir.resolve()
    target_dir.mkdir(parents=True, exist_ok=True)

    to_check = members if members is not None else tar.getmembers()
    # Pre-check every member (works for all py versions)
    for member in to_check:
        if member.name.startswith(("/", "\\")) or ".." in Path(member.name).parts:
            raise RuntimeError(f"Unsafe tar member (path traversal): {member.name}")
        dest = (target_dir / member.name).resolve()
        if not str(dest).startswith(str(target_dir)):
            raise RuntimeError(f"Unsafe tar member (escapes target): {member.name}")

    # Use modern filter when available (Python 3.12+)
    if sys.version_info >= (3, 12):
        tar.extractall(target_dir, members=members, filter="data")
    else:
        tar.extractall(target_dir, members=members)


# --- Pricing (simple static table; update periodically) ---
# Prices are per 1M tokens (USD). Rough placeholders for Grok models.
MODEL_PRICES: dict[str, dict[str, float]] = {
    "grok-build": {"input": 3.0, "output": 15.0},
    "grok-3": {"input": 2.0, "output": 10.0},
    "grok-3-mini": {"input": 0.5, "output": 2.5},
    "grok-2": {"input": 2.0, "output": 8.0},
    # add more as models_cache reveals them
    "default": {"input": 2.0, "output": 10.0},
}


def estimate_cost(
    messages_or_tokens: int, model: str = "grok-build", is_output: bool = False
) -> float:
    """Very rough cost estimate. messages_or_tokens can be token count or approx messages*avg.
    For accuracy feed real token counts from signals or usage.
    """
    prices = MODEL_PRICES.get(model.lower(), MODEL_PRICES["default"])
    key = "output" if is_output else "input"
    per_m = prices.get(key, 10.0)
    return (messages_or_tokens / 1_000_000.0) * per_m


def load_toml(path: Path) -> dict[str, Any]:
    """Load a .toml file robustly.

    - Prefers tomllib (Python >= 3.11 stdlib)
    - Falls back to tomli (backport, installed only on <3.11 via deps)
    - Final naive line-based parser for simple cases (no real TOML features needed for grok config)
    Returns {} on missing file or any parse/read error. Never raises to caller.
    """
    if not path.exists():
        return {}

    # Python 3.11+ stdlib
    if sys.version_info >= (3, 11):
        try:
            import tomllib

            with open(path, "rb") as f:
                return tomllib.load(f)  # type: ignore[no-any-return]
        except Exception:  # tomllib can raise various on bad toml; fallback
            pass  # fall through to next strategy

    # tomli backport
    try:
        import tomli

        with open(path, "rb") as f:
            return tomli.load(f)  # type: ignore[no-any-return]
    except ImportError:
        pass
    except Exception:  # bad toml content etc; fallback
        pass

    # Very naive fallback (supports [section], [section.sub], key = "value", skips # comments)
    data: dict[str, Any] = {}
    current_dict: dict[str, Any] | None = None
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
        for raw in text.splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("[") and line.endswith("]"):
                section = line[1:-1].strip()
                parts = [p.strip() for p in section.split(".") if p.strip()]
                cur: dict[str, Any] = data
                for p in parts:
                    if p not in cur or not isinstance(cur.get(p), dict):
                        cur[p] = {}
                    cur = cur[p]
                current_dict = cur
            elif "=" in line and current_dict is not None:
                k, v = [x.strip().strip("\"'") for x in line.split("=", 1)]
                current_dict[k] = v
    except (OSError, UnicodeDecodeError, ValueError, KeyError, IndexError):
        return {}
    return data


# --- Safe FS/JSON helpers to reduce broad exception handling in callers ---
def safe_read_text(
    path: Path, *, encoding: str = "utf-8", errors: str = "ignore", default: str = ""
) -> str:
    """Read text file; return default on any read/decode error."""
    try:
        return path.read_text(encoding=encoding, errors=errors)
    except Exception:
        return default


def safe_json_load(path: Path | str, default: Any | None = None) -> Any:
    """json.loads on file content or string; returns default ({} if None) on error."""
    if default is None:
        default = {}
    try:
        if isinstance(path, (str, Path)) and Path(path).exists():
            text = safe_read_text(Path(path))
        else:
            text = str(path)
        import json

        return json.loads(text)
    except Exception:
        return default
