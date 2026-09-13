"""Legacy usage report (session summaries) and rough cost (message×400)."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import typer

from ..utils.common import (
    SessionSummary,
    console,
    estimate_cost,
    format_age,
    get_grok_home,
    iter_sessions,
    make_table,
    warn,
)
from ..utils.usage_display import bucket_cut_caption, shown_bucket_count


def ascii_bar(value: float, maxv: float, width: int = 24) -> str:
    if maxv <= 0:
        return ""
    filled = int((value / maxv) * width)
    filled = max(0, min(width, filled))
    return "█" * filled + "░" * (width - filled)


def sparkline(values: list[int], width: int = 20) -> str:
    if not values:
        return ""
    blocks = "▁▂▃▄▅▆▇█"
    mx = max(values) or 1
    scaled = [int((v / mx) * (len(blocks) - 1)) for v in values]
    return "".join(blocks[min(s, len(blocks) - 1)] for s in scaled[-width:])


def print_legacy_session_report(
    grok_home: Path,
    *,
    since: str | None,
    date_from: str | None,
    by: str,
    top: int,
    show_all: bool = False,
    json_out: bool,
) -> None:
    """Session-summary report (messages/sessions — no list$/est$)."""
    sessions = list(iter_sessions(grok_home))

    if since or date_from:
        raw = date_from or since
        try:
            cutoff = datetime.fromisoformat(raw).replace(tzinfo=timezone.utc)  # type: ignore[arg-type]
            sessions = [
                s
                for s in sessions
                if (s.created_at or datetime.min.replace(tzinfo=timezone.utc)) >= cutoff
            ]
        except (ValueError, TypeError, OverflowError):
            warn(f"Ignoring bad date filter {raw}")

    if not sessions:
        warn("No data for report.")
        return

    group_by = by if by in ("project", "model", "day") else "project"
    groups: defaultdict[str, list[SessionSummary]] = defaultdict(list)
    for s in sessions:
        key = {
            "project": s.cwd,
            "model": s.current_model_id,
            "day": (s.created_at or datetime.now(timezone.utc)).strftime("%Y-%m-%d"),
        }[group_by]
        groups[key].append(s)

    rows = []
    for k, ss in groups.items():
        msgs = sum(x.num_messages for x in ss)
        actives: list[datetime] = []
        for x in ss:
            dt = x.last_active_at or x.created_at
            if dt:
                actives.append(dt)
        last = max(actives) if actives else None
        rows.append((k, len(ss), msgs, last))

    rows.sort(key=lambda r: (-r[1], -r[2]))
    shown_n = shown_bucket_count(len(rows), top, show_all)
    shown = rows[:shown_n]
    cut = bucket_cut_caption(shown_n, len(rows))

    if json_out:
        import json

        print(
            json.dumps(
                [
                    {
                        "key": r[0],
                        "sessions": r[1],
                        "messages": r[2],
                        "last": r[3].isoformat() if r[3] else None,
                    }
                    for r in shown
                ],
                indent=2,
            )
        )
        return

    title = f"Usage by {group_by} (legacy sessions/messages, {cut}, {len(sessions)} sessions)"
    t = make_table(title, ["Key", "Sessions", "Messages", "Last Active", "Share"])
    max_sess = max((r[1] for r in shown), default=1) or 1
    for k, nsess, nmsg, last in shown:
        share = ascii_bar(nsess, max_sess, 18)
        t.add_row(
            k[:48] + ("…" if len(k) > 48 else ""),
            str(nsess),
            str(nmsg),
            format_age(last),
            share,
        )
    console.print(t)
    console.print(
        "\n[dim]Tip: list$/est$ →  grok-utils usage report --by app --from YYYY-MM-DD\n"
        "     (above is legacy sessions/messages only. For day with list$:\n"
        "      grok-utils usage report --by day --tokens --from YYYY-MM-DD)[/dim]"
    )

    days: defaultdict[str, int] = defaultdict(int)
    for s in sessions:
        d = (s.created_at or datetime.now(timezone.utc)).strftime("%Y-%m-%d")
        days[d] += 1
    recent = sorted(days.items())[-14:]
    vals = [v for _, v in recent]
    if vals:
        console.print(
            f"\n[bold]Recent activity spark (last {len(vals)} days):[/bold] "
            f"{sparkline(vals)}  (max {max(vals)})"
        )


def print_cost_rough(
    ctx: typer.Context,
    *,
    since: str | None,
    by: str,
    top: int,
    show_all: bool = False,
    json_out: bool,
) -> None:
    """Legacy message×400 × static MODEL_PRICES estimate."""
    grok_home = get_grok_home(ctx.obj.get("grok_home") if ctx.obj else None)
    sessions = list(iter_sessions(grok_home))

    if since:
        try:
            cutoff = datetime.fromisoformat(since).replace(tzinfo=timezone.utc)
            sessions = [
                s
                for s in sessions
                if (s.created_at or datetime.min.replace(tzinfo=timezone.utc)) >= cutoff
            ]
        except (ValueError, TypeError, OverflowError):
            warn(f"Ignoring bad --since {since}")

    if not sessions:
        warn("No data.")
        return

    groups: defaultdict[str, list[SessionSummary]] = defaultdict(list)
    for s in sessions:
        key = s.current_model_id if by == "model" else s.cwd
        groups[key].append(s)

    rows = []
    total_est = 0.0
    for k, ss in groups.items():
        tokens = sum(s.num_messages for s in ss) * 400
        model = ss[0].current_model_id if ss else "grok-build"
        est = estimate_cost(tokens, model=model, is_output=True)
        est += estimate_cost(int(tokens * 0.6), model=model, is_output=False)
        total_est += est
        rows.append((k, len(ss), round(est, 2)))

    rows.sort(key=lambda r: -r[2])
    shown_n = shown_bucket_count(len(rows), top, show_all)
    shown = rows[:shown_n]
    cut = bucket_cut_caption(shown_n, len(rows))

    if json_out:
        import json

        print(
            json.dumps(
                {
                    "mode": "rough",
                    "estimated_total_usd": round(total_est, 2),
                    "by": by,
                    "top": shown,
                },
                indent=2,
            )
        )
        return

    t = make_table(
        f"Estimated Cost by {by} (ROUGH proxy, USD, {cut})",
        ["Key", "Sessions", "Est. $"],
    )
    for k, ns, est in shown:
        t.add_row(k[:48] + ("…" if len(k) > 48 else ""), str(ns), f"{est:.2f}")
    console.print(t)
    console.print(f"\n[bold]Grand total (rough proxy): ${total_est:.2f}[/bold]")
    warn(
        "Legacy rough mode (message count × assumed tokens × static prices). "
        "Prefer default token mode. See: grok-utils usage info"
    )
