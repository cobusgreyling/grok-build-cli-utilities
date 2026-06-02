"""grok-utils usage - gorgeous analytics for Grok Build power users."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Optional

import typer
from rich.table import Table

from ..utils.common import (
    SessionSummary,
    console,
    format_age,
    get_grok_home,
    iter_sessions,
    make_table,
    warn,
)

app = typer.Typer(help="Usage reports, leaderboards and trends", no_args_is_help=True)


def _sparkline(values: list[int], width: int = 20) -> str:
    """Simple unicode sparkline."""
    if not values:
        return ""
    blocks = "▁▂▃▄▅▆▇█"
    mx = max(values) or 1
    scaled = [int((v / mx) * (len(blocks) - 1)) for v in values]
    return "".join(blocks[min(s, len(blocks) - 1)] for s in scaled[-width:])


def _ascii_bar(value: int, maxv: int, width: int = 24) -> str:
    if maxv == 0:
        return ""
    filled = int((value / maxv) * width)
    return "█" * filled + "░" * (width - filled)


@app.command("report")
def report(
    ctx: typer.Context,
    since: Optional[str] = typer.Option(None, "--since", help="e.g. 2026-05-01"),
    by: str = typer.Option("project", "--by", help="Group by: project | model | day"),
    top: int = typer.Option(10, "--top", help="Show top N"),
    json_out: bool = typer.Option(False, "--json"),
) -> None:
    """Generate a rich usage report."""
    grok_home = get_grok_home(ctx.obj.get("grok_home") if ctx.obj else None)
    sessions = list(iter_sessions(grok_home))

    if since:
        try:
            cutoff = datetime.fromisoformat(since).replace(tzinfo=timezone.utc)
            sessions = [s for s in sessions if (s.created_at or datetime.min.replace(tzinfo=timezone.utc)) >= cutoff]
        except Exception:
            warn(f"Ignoring bad --since {since}")

    if not sessions:
        warn("No data for report.")
        return

    groups: defaultdict[str, list[SessionSummary]] = defaultdict(list)
    for s in sessions:
        key = {
            "project": s.cwd,
            "model": s.current_model_id,
            "day": (s.created_at or datetime.now(timezone.utc)).strftime("%Y-%m-%d"),
        }[by]
        groups[key].append(s)

    rows = []
    for k, ss in groups.items():
        msgs = sum(x.num_messages for x in ss)
        last = max((x.last_active_at or x.created_at for x in ss if x.last_active_at or x.created_at), default=None)
        rows.append((k, len(ss), msgs, last))

    rows.sort(key=lambda r: (-r[1], -r[2]))

    if json_out:
        import json
        console.print(json.dumps(
            [{"key": r[0], "sessions": r[1], "messages": r[2], "last": r[3].isoformat() if r[3] else None} for r in rows[:top]],
            indent=2,
        ))
        return

    title = f"Usage by {by} (top {top}, {len(sessions)} total sessions)"
    t = make_table(title, ["Key", "Sessions", "Messages", "Last Active", "Share"])
    max_sess = max(r[1] for r in rows) or 1
    for k, nsess, nmsg, last in rows[:top]:
        share = _ascii_bar(nsess, max_sess, 18)
        t.add_row(
            k[:48] + ("…" if len(k) > 48 else ""),
            str(nsess),
            str(nmsg),
            format_age(last),
            share,
        )
    console.print(t)

    # mini spark of activity last 14 days
    days: defaultdict[str, int] = defaultdict(int)
    for s in sessions:
        d = (s.created_at or datetime.now(timezone.utc)).strftime("%Y-%m-%d")
        days[d] += 1
    recent = sorted(days.items())[-14:]
    vals = [v for _, v in recent]
    if vals:
        console.print(f"\n[bold]Recent activity spark (last {len(vals)} days):[/bold] {_sparkline(vals)}  (max {max(vals)})")


@app.command("top-projects")
def top_projects(ctx: typer.Context, n: int = typer.Option(8, "--count", "-n")) -> None:
    """Leaderboard of projects by session count and activity."""
    grok_home = get_grok_home(ctx.obj.get("grok_home") if ctx.obj else None)
    sessions = list(iter_sessions(grok_home))

    proj: defaultdict[str, dict] = defaultdict(lambda: {"count": 0, "msgs": 0, "last": None})
    for s in sessions:
        p = proj[s.cwd]
        p["count"] += 1
        p["msgs"] += s.num_messages
        act = s.last_active_at or s.created_at
        if act and (not p["last"] or act > p["last"]):
            p["last"] = act

    ranked = sorted(proj.items(), key=lambda kv: (-kv[1]["count"], -kv[1]["msgs"]))[:n]

    t = make_table("Top Projects", ["Project", "Sessions", "Messages", "Last Used"])
    for path, data in ranked:
        short = path if len(path) < 50 else "…" + path[-49:]
        t.add_row(short, str(data["count"]), str(data["msgs"]), format_age(data["last"]))
    console.print(t)


@app.command("models")
def models_usage(ctx: typer.Context) -> None:
    """Model distribution and preferences."""
    grok_home = get_grok_home(ctx.obj.get("grok_home") if ctx.obj else None)
    sessions = list(iter_sessions(grok_home))

    counts: defaultdict[str, int] = defaultdict(int)
    for s in sessions:
        counts[s.current_model_id] += 1

    if not counts:
        return

    t = make_table("Model Usage", ["Model", "Sessions", "Share"])
    mx = max(counts.values())
    for m, c in sorted(counts.items(), key=lambda x: -x[1]):
        bar = _ascii_bar(c, mx, 30)
        pct = f"{100 * c / len(sessions):.1f}%"
        t.add_row(m, f"{c} ({pct})", bar)
    console.print(t)


@app.command("timeline")
def timeline(ctx: typer.Context, days: int = typer.Option(30, "--days", "-d")) -> None:
    """Daily activity over the last N days."""
    grok_home = get_grok_home(ctx.obj.get("grok_home") if ctx.obj else None)
    sessions = list(iter_sessions(grok_home))

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    buckets: defaultdict[str, int] = defaultdict(int)
    for s in sessions:
        if s.created_at and s.created_at >= cutoff:
            key = s.created_at.strftime("%m-%d")
            buckets[key] += 1

    if not buckets:
        warn("No recent activity.")
        return

    t = Table(title=f"Daily Sessions (last {days}d)", show_header=False, box=None)
    maxv = max(buckets.values()) or 1
    for day in sorted(buckets.keys()):
        bar = _ascii_bar(buckets[day], maxv, 28)
        t.add_row(day, bar, str(buckets[day]))
    console.print(t)
