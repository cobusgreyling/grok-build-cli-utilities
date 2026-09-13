"""grok-utils usage - gorgeous analytics for Grok Build power users."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta, timezone, tzinfo
from pathlib import Path

import typer
from rich.progress import Progress
from rich.table import Table

from ..utils.auth_status import iso_or_none
from ..utils.common import (
    console,
    format_age,
    get_grok_home,
    get_sessions_dir,
    iter_sessions,
    make_table,
    warn,
)
from ..utils.pricing import (
    DEFAULT_CASH_SCALE,
    effective_rates,
    list_rate_profiles,
    load_plan_advisor_config,
    load_usage_config,
    plan_advisor,
    resolve_topoff_discount_scenarios,
    resolve_topoff_pack_usd,
)
from ..utils.usage_cost_window import api_scale_for_advisor, build_token_cost_window
from ..utils.usage_display import (
    DEFAULT_BUCKET_TOP,
    bucket_cut_caption,
    cfg_overage_scale,
    fmt_tokens,
    format_auth_plan_advisor_line,
    plan_advisor_export,
    print_api_breakdown,
    print_bucket_cut_note,
    print_plan_advisor,
    print_token_cost_summary,
    shown_bucket_count,
    week_list_series,
)
from ..utils.usage_faq import COST_CAVEATS_LONG
from ..utils.usage_tokens import (
    COST_GROUPS,
    TOKEN_REPORT_GROUPS,
    UNSPLIT_MULTI_PR_NOTE,
    CreatedPr,
    UsageRec,
    allocate_invoice,
    disambiguate_display_keys,
    filter_usage,
    list_price_usd,
    load_turn_usage,
    parse_iso_date,
    pr_group_key,
    resolve_usage_date_tz,
    session_display_key,
    sorted_pr_labels,
    usage_calendar_date,
)
from .usage_legacy import print_cost_rough, print_legacy_session_report

app = typer.Typer(help="Usage reports, leaderboards and trends", no_args_is_help=True)

_FROM_HELP = (
    "Inclusive local calendar start YYYY-MM-DD. Same clock as weekly resets "
    "and Build /usage. Omit --to for through latest"
)
_TO_HELP = (
    "Inclusive local calendar end YYYY-MM-DD. Same clock as --from. "
    "Omit for through latest session data"
)
_SINCE_HELP = "Alias for --from (local calendar YYYY-MM-DD)"
_TZ_HELP = (
    "Calendar zone for --from/--to/--since and --by day. "
    "local (default) | UTC | IANA (America/New_York). "
    "CLI wins over usage.date_tz in grok-utils.toml"
)
_TOP_HELP = "Show top N buckets by list$. --all overrides this."
_ALL_HELP = "Print every bucket. Overrides --top."


def _sparkline(values: list[int], width: int = 20) -> str:
    """Simple unicode sparkline."""
    if not values:
        return ""
    blocks = "▁▂▃▄▅▆▇█"
    mx = max(values) or 1
    scaled = [int((v / mx) * (len(blocks) - 1)) for v in values]
    return "".join(blocks[min(s, len(blocks) - 1)] for s in scaled[-width:])


def _ascii_bar(value: float, maxv: float, width: int = 24) -> str:
    if maxv <= 0:
        return ""
    filled = int((value / maxv) * width)
    filled = max(0, min(width, filled))
    return "█" * filled + "░" * (width - filled)


def _fmt_tokens(n: int) -> str:
    return fmt_tokens(n)


def _data_date_span(records: list[UsageRec], tz: tzinfo) -> tuple[date | None, date | None]:
    """Earliest and latest turn dates in the usage calendar zone."""
    if not records:
        return None, None
    days = [usage_calendar_date(r.ts, tz) for r in records]
    return min(days), max(days)


def _resolve_date_tz(grok_home: Path, cli_tz: str | None) -> tuple[tzinfo, str]:
    cfg = load_usage_config(grok_home)
    raw = cfg.get("date_tz")
    cfg_tz = raw.strip() if isinstance(raw, str) else None
    try:
        return resolve_usage_date_tz(cli=cli_tz, config=cfg_tz)
    except ValueError as exc:
        _warn_stderr(str(exc))
        raise typer.Exit(code=1) from exc


def _warn_stderr(msg: str) -> None:
    """Warn on stderr so --json stdout stays pure."""
    import sys

    from rich.console import Console as RichConsole

    RichConsole(file=sys.stderr).print(f"[yellow]⚠[/yellow] {msg}")


def _load_filtered_usage(
    grok_home: Path,
    *,
    since: str | None,
    date_from: str | None,
    date_to: str | None,
    apps: list[str] | None,
    tz: tzinfo,
) -> tuple[
    list[UsageRec],
    date | None,
    date | None,
    date | None,
    date | None,
    dict[str, list[CreatedPr]],
]:
    """Load turns, apply filters, warn if CLI range extends past available data.

    Returns (filtered, d_from, d_to, data_earliest, data_latest, prs_by_session)
    where data_* are the min/max dates in session logs (app-filtered, before
    date window).
    """
    import sys

    from rich.console import Console as RichConsole

    sessions_dir = get_sessions_dir(grok_home)
    # Progress on stderr so --json stdout stays pure
    prs_raw: dict[str, dict[str, CreatedPr]] = {}
    with Progress(console=RichConsole(file=sys.stderr), transient=True) as progress:
        records = load_turn_usage(sessions_dir, progress=progress, prs_by_session=prs_raw)
    prs_by_session = {sid: list(found.values()) for sid, found in prs_raw.items()}

    d_from = None
    d_to = None
    if date_from:
        try:
            d_from = parse_iso_date(date_from)
        except ValueError:
            warn(f"Ignoring bad --from {date_from}")
    if date_to:
        try:
            d_to = parse_iso_date(date_to)
        except ValueError:
            warn(f"Ignoring bad --to {date_to}")
    if since and d_from is None:
        try:
            d_from = parse_iso_date(since)
        except ValueError:
            warn(f"Ignoring bad --since {since}")

    # Universe for span checks: app filter only (ignore date window)
    base = filter_usage(records, apps=apps, tz=tz) if apps else records
    earliest, latest = _data_date_span(base, tz)

    if d_from is not None and earliest is not None and d_from < earliest:
        _warn_stderr(
            f"--from {d_from.isoformat()} is before earliest session data "
            f"({earliest.isoformat()}). No turns exist before {earliest.isoformat()}; "
            f"report starts from that date."
        )
    if d_to is not None and latest is not None and d_to > latest:
        _warn_stderr(
            f"--to {d_to.isoformat()} is after latest session data "
            f"({latest.isoformat()}). Report ends at {latest.isoformat()}."
        )
    if d_from is not None and latest is not None and d_from > latest:
        _warn_stderr(
            f"--from {d_from.isoformat()} is after latest session data "
            f"({latest.isoformat()}). No turns match this window."
        )
    if d_to is not None and earliest is not None and d_to < earliest:
        _warn_stderr(
            f"--to {d_to.isoformat()} is before earliest session data "
            f"({earliest.isoformat()}). No turns match this window."
        )

    filtered = filter_usage(records, date_from=d_from, date_to=d_to, apps=apps, tz=tz)
    return filtered, d_from, d_to, earliest, latest, prs_by_session


def _records_for_group(
    records: list[UsageRec],
    group: str,
    prs_by_session: dict[str, list[CreatedPr]],
    *,
    include_unlabeled: bool,
) -> list[UsageRec]:
    if group != "pr" or include_unlabeled:
        return records
    labeled = {sid for sid, prs in prs_by_session.items() if prs}
    return [r for r in records if r.session_id in labeled]


def _prs_for_bucket(key: str, group: str, prs_by_session: dict[str, list[CreatedPr]]) -> list[str]:
    if group == "session":
        return sorted_pr_labels(prs_by_session.get(key, ()))
    if group != "pr":
        return []
    for sid, created in prs_by_session.items():
        if pr_group_key(sid, created) == key:
            return sorted_pr_labels(created)
        if key == sid:
            return sorted_pr_labels(created)
    return []


def _projects_by_session(records: list[UsageRec]) -> dict[str, str]:
    out: dict[str, str] = {}
    for r in records:
        if r.session_id and r.project and r.session_id not in out:
            out[r.session_id] = r.project
    return out


def _display_bucket_key(
    key: str,
    group: str,
    prs_by_session: dict[str, list[CreatedPr]],
    *,
    width: int,
    projects_by_session: dict[str, str] | None = None,
) -> str:
    if group == "session":
        shown = session_display_key(
            key,
            prs_by_session.get(key, ()),
            project=(projects_by_session or {}).get(key, ""),
        )
    else:
        shown = key
    if width <= 0 or len(shown) <= width:
        return shown
    return shown[:width] + "…"


def _row_display_keys(
    keys: list[str],
    group: str,
    prs_by_session: dict[str, list[CreatedPr]],
    records: list[UsageRec],
) -> list[str]:
    projects = _projects_by_session(records)
    labels = [
        _display_bucket_key(
            key,
            group,
            prs_by_session,
            width=0,
            projects_by_session=projects,
        )
        for key in keys
    ]
    return disambiguate_display_keys(keys, labels)


def _maybe_print_unsplit_pr_note(
    group: str,
    keys: list[str],
    prs_by_session: dict[str, list[CreatedPr]],
) -> None:
    if group != "pr":
        return
    for key in keys:
        if len(_prs_for_bucket(key, group, prs_by_session)) > 1:
            console.print(f"[dim]{UNSPLIT_MULTI_PR_NOTE}[/dim]")
            return


@app.command("report")
def report(
    ctx: typer.Context,
    since: str | None = typer.Option(None, "--since", metavar="DATE", help=_SINCE_HELP),
    date_from: str | None = typer.Option(None, "--from", metavar="DATE", help=_FROM_HELP),
    date_to: str | None = typer.Option(None, "--to", metavar="DATE", help=_TO_HELP),
    tz: str | None = typer.Option(None, "--tz", metavar="ZONE", help=_TZ_HELP),
    by: str = typer.Option(
        "app",
        "--by",
        help=(
            "Group by: app (repo from cwd, default, list$/est$) | project (full cwd, "
            "list$/est$ with --tokens) | model | day | session | pr. "
            "--tokens required for project/model/day; ignored with --by app|session|pr"
        ),
    ),
    top: int = typer.Option(DEFAULT_BUCKET_TOP, "--top", metavar="N", help=_TOP_HELP),
    show_all: bool = typer.Option(False, "--all", help=_ALL_HELP),
    tokens: bool = typer.Option(
        False,
        "--tokens",
        help=(
            "Use turn-level tokens + list$/est$ (same as usage cost). "
            "Redundant with --by app|session|pr (already on). Needed for "
            "--by project|model|day to leave the legacy session-summary path"
        ),
    ),
    rates_model: str | None = typer.Option(
        None,
        "--rates-model",
        "-m",
        help=(
            "Force a reconstructed list-rate table (ignores costUsdTicks). "
            f"Omit to use Build /usage Cost (ticks÷1e10). "
            f"Choices: {', '.join(list_rate_profiles())}"
        ),
    ),
    cash_scale: float | None = typer.Option(
        None,
        "--cash-scale",
        metavar="SCALE",
        help=(
            "Requires number: force uniform list$ → est$ scale (else path/regime "
            "auth mix like usage cost). Optional: usage.cash_scale in toml"
        ),
    ),
    json_out: bool = typer.Option(False, "--json", help="Flag (no value): machine-readable JSON"),
) -> None:
    """Generate a rich usage report.

    Token path (list$ + est$, same path/regime + auth mix as usage cost):
      · always when --by app | session | pr
      · also when --tokens (for --by project | model | day)
    Without --tokens, --by project|model|day uses the legacy session-summary path
    (message counts, not list$/est$). Share bars use list$ on the token path.
    """
    grok_home = get_grok_home(ctx.obj.get("grok_home") if ctx.obj else None)
    date_tz, date_tz_label = _resolve_date_tz(grok_home, tz)

    # --by app|session|pr implies token path; --tokens is only meaningful otherwise
    if tokens and by in ("app", "session", "pr"):
        warn(
            "--tokens is ignored with --by app|session|pr "
            "(token path / list$/est$ is already on). "
            "Use --tokens when grouping by project, model, or day, e.g.\n"
            "  grok-utils usage report --by day --tokens --from 2026-08-01"
        )
    use_tokens = bool(tokens) or by in ("app", "session", "pr")

    if use_tokens:
        group = by if by in TOKEN_REPORT_GROUPS else "app"
        records, d_from, d_to, data_earliest, data_latest, prs_by_session = _load_filtered_usage(
            grok_home, since=since, date_from=date_from, date_to=date_to, apps=None, tz=date_tz
        )
        records = _records_for_group(records, group, prs_by_session, include_unlabeled=False)
        if not records:
            warn("No turn usage data for report (try without --tokens for summary-based report).")
            return
        result_earliest, result_latest = _data_date_span(records, date_tz)
        win = build_token_cost_window(
            grok_home,
            records,
            group=group,
            rates_model=rates_model,
            cash_scale=cash_scale,
            d_from=d_from,
            d_to=d_to,
            data_earliest=data_earliest,
            data_latest=data_latest,
            result_earliest=result_earliest,
            result_latest=result_latest,
            prs_by_session=prs_by_session,
            date_tz=date_tz,
        )

        shown_n = shown_bucket_count(len(win.buckets), top, show_all)
        shown_buckets = win.buckets[:shown_n]
        cut = bucket_cut_caption(shown_n, len(win.buckets))

        if json_out:
            import json

            top_rows = []
            for b in shown_buckets:
                list_b = win.list_for_key(b.key)
                row = b.to_dict(win.rates)
                row["list_usd"] = round(list_b, 4)
                row["api_est_usd"] = round(list_b, 4)
                row["est_usd"] = round(win.est_for_key(b.key), 4)
                prs = _prs_for_bucket(b.key, group, prs_by_session)
                if prs:
                    row["prs"] = prs
                top_rows.append(row)

            print(
                json.dumps(
                    {
                        "mode": "tokens",
                        "by": group,
                        "from": d_from.isoformat() if d_from else None,
                        "to": d_to.isoformat() if d_to else None,
                        "date_tz": date_tz_label,
                        "result_from": (result_earliest.isoformat() if result_earliest else None),
                        "result_to": (result_latest.isoformat() if result_latest else None),
                        "rates_model": win.rates_label,
                        "list_source": win.list_source,
                        "rates": win.rates.as_dict(),
                        "cash_scale": win.cash_scale_val,
                        "cash_scale_source": win.cash_scale_src,
                        "topoff_discount": win.topoff_d,
                        "topoff_discount_source": win.topoff_src,
                        "auth": win.auth_st.as_dict(),
                        "weekly_usage_pct": win.weekly_pct,
                        "weekly_period_start": iso_or_none(win.weekly_period_start),
                        "weekly_resets_at": iso_or_none(win.weekly_period_end),
                        "prepaid_balance_usd": win.prepaid_balance,
                        "auth_mix": win.mix.as_dict(),
                        "totals": {
                            **win.tot.to_dict(win.rates),
                            "list_usd": round(win.list_total, 4),
                            "api_est_usd": round(win.list_total, 4),
                            "est_usd": round(win.est_total, 4),
                            "est_cash_usd": round(win.est_cash_total, 4),
                        },
                        "buckets": top_rows,
                        "caveats": [
                            "list$_is_costUsdTicks_div_1e10_when_present_else_rates",
                            "est$_uses_auth_timeline_mix_unless_uniform_override",
                            "share_bars_use_list$",
                            "est_cash$_applies_topoff_discount_to_est$",
                        ],
                    },
                    indent=2,
                )
            )
            return

        period = ""
        if result_earliest or result_latest:
            left = result_earliest.isoformat() if result_earliest else "…"
            right = result_latest.isoformat() if result_latest else "…"
            period = f" · {left} → {right}"
            if d_from is not None and result_earliest is not None and d_from < result_earliest:
                period += f"  (requested --from {d_from.isoformat()})"
        title = (
            f"Usage by {group} (list$ primary · est$=path scale, {cut}, "
            f"{win.tot.n} prompts, {_fmt_tokens(win.tot.total)} tok){period}"
        )
        t = make_table(
            title,
            ["Key", "Prm", "Tokens", "Cache%", "list$", "est$", "Share(list$)", "Share(tok)"],
            no_wrap=("Key",),
        )
        row_keys = _row_display_keys(
            [b.key for b in shown_buckets],
            group,
            prs_by_session,
            records,
        )
        max_list = max((win.list_for_key(b.key) for b in shown_buckets), default=1.0) or 1.0
        max_tok = max((b.total for b in shown_buckets), default=1) or 1
        for b, key in zip(shown_buckets, row_keys, strict=True):
            list_b = win.list_for_key(b.key)
            est_b = win.est_for_key(b.key)
            t.add_row(
                key,
                str(b.n),
                _fmt_tokens(b.total),
                f"{b.cache_pct:.1f}%",
                f"{list_b:.2f}",
                f"{est_b:.2f}",
                _ascii_bar(list_b, max_list, 12),
                _ascii_bar(float(b.total), float(max_tok), 12),
            )
        console.print(t)
        print_bucket_cut_note(shown_n, len(win.buckets))
        _maybe_print_unsplit_pr_note(group, [b.key for b in shown_buckets], prs_by_session)
        print_token_cost_summary(win, cost_mode=False, show_faq_hint=False)
        from ..utils.usage_tokens import aggregate as _agg

        day_buckets = _agg(records, "day")
        vals = [b.total for b in day_buckets[-14:]]
        if vals:
            console.print(
                f"[dim]Daily tokens[/dim]  {_sparkline(vals)}  "
                f"(last {len(vals)}d · max {_fmt_tokens(max(vals))})"
            )
        console.print(
            "\n[dim]FAQ: grok-utils usage info"
            "  ·  cost detail: grok-utils usage cost … -P"
            "  ·  wallet: grok-utils auth status[/dim]"
        )
        return

    # Legacy summary.json path (sessions/messages only)
    print_legacy_session_report(
        grok_home,
        since=since,
        date_from=date_from,
        by=by,
        top=top,
        show_all=show_all,
        json_out=json_out,
    )


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


@app.command("info")
def cost_info() -> None:
    """FAQ: why list$/est$ differ from Build Session Cost, Credits, weekly limit."""
    # markup=False so toml [usage] brackets are not treated as Rich tags
    console.print(COST_CAVEATS_LONG, markup=False)


@app.command("cost")
def cost_report(
    ctx: typer.Context,
    since: str | None = typer.Option(None, "--since", metavar="DATE", help=_SINCE_HELP),
    date_from: str | None = typer.Option(None, "--from", metavar="DATE", help=_FROM_HELP),
    date_to: str | None = typer.Option(None, "--to", metavar="DATE", help=_TO_HELP),
    tz: str | None = typer.Option(None, "--tz", metavar="ZONE", help=_TZ_HELP),
    by: str = typer.Option(
        "app",
        "--by",
        metavar="KEY",
        help=(
            "Group cost by: app | project | model | day | week | month | session | pr. "
            "app is the repo inferred from cwd (issue and Grok worktrees roll up). "
            "session and pr Keys need one Grok Build "
            "session per unit of work, cwd in that repo, and github "
            "create_pull_request OkayOutput or gh pr create stdout in "
            "updates.jsonl. session = repo#issue or project name, never a "
            "session UUID. pr = repo#issue (Fixes or Closes) or repo#PR; "
            "several PRs stay one row (widgets #12,15), never split; "
            "mixed-repo keys compact (widgets #7,8,14 · notes #15); "
            "colliding Keys keep two rows (notes#22 · 01a05e3c…); "
            "no session UUID in the pr key; "
            "sessions with no created PR are omitted unless --include-unlabeled"
        ),
    ),
    top: int = typer.Option(DEFAULT_BUCKET_TOP, "--top", metavar="N", help=_TOP_HELP),
    show_all: bool = typer.Option(False, "--all", help=_ALL_HELP),
    mode: str = typer.Option(
        "tokens",
        "--mode",
        metavar="MODE",
        help="tokens (default, turn usage) | rough (legacy message×400)",
    ),
    invoice_usd: float | None = typer.Option(
        None,
        "--invoice-usd",
        metavar="USD",
        help=(
            "Requires amount: total SuperGrok/cash $ to allocate by costUsdTicks "
            "(e.g. --invoice-usd 180). Optional companion: --fixed-usd 30"
        ),
    ),
    fixed_usd: float = typer.Option(
        0.0,
        "--fixed-usd",
        metavar="USD",
        help="Requires amount with --invoice-usd: fixed fee amortized across buckets (e.g. 30)",
    ),
    rates_model: str | None = typer.Option(
        None,
        "--rates-model",
        "-m",
        metavar="MODEL",
        help=(
            "Force a reconstructed list-rate table (ignores costUsdTicks). "
            f"Omit to use Build /usage Cost (ticks÷1e10). "
            f"Choices: {', '.join(list_rate_profiles())}"
        ),
    ),
    cash_scale: float | None = typer.Option(
        None,
        "--cash-scale",
        metavar="SCALE",
        help=(
            f"Requires number: scale list$ → est$ (e.g. --cash-scale 0.57). "
            f"Default {DEFAULT_CASH_SCALE}; or set usage.cash_scale in ~/.grok/grok-utils.toml"
        ),
    ),
    prepaid_usd: float | None = typer.Option(
        None,
        "--prepaid-usd",
        metavar="USD",
        help=(
            "Requires amount: prepaid loaded for window (e.g. --prepaid-usd 60). "
            "Use together with --credits-remaining"
        ),
    ),
    credits_remaining: float | None = typer.Option(
        None,
        "--credits-remaining",
        metavar="USD",
        help=(
            "Requires amount: credits left in Build UI (e.g. --credits-remaining 28.12). "
            "Use together with --prepaid-usd → burn/list scale"
        ),
    ),
    topoff_discount: float | None = typer.Option(
        None,
        "--topoff-discount",
        metavar="FRAC",
        help=(
            "Requires 0..1: model Extra Credits pack promo "
            "(0=full price, 0.25=−25%, 1.0=free tops). "
            "Default 0; or usage.topoff_discount in toml. Affects est_cash$ + plan scenarios."
        ),
    ),
    list_price: bool = typer.Option(
        False,
        "--list-price",
        help="Flag (no value): show costUsdTicks÷1e10 (same $ as /usage Session Cost)",
    ),
    api_estimate: bool = typer.Option(
        False,
        "--api-estimate",
        help="Flag (no value): print pure-API list-rate breakdown for filtered total",
    ),
    plan_advisor_flag: bool = typer.Option(
        False,
        "--plan-advisor",
        "-P",
        help=(
            "Flag (no value): compare pure API vs SuperGrok vs SuperGrok Heavy "
            "for this window (run-rate + monthly projection). "
            "Weekly pool sizes are estimates."
        ),
    ),
    detail: bool = typer.Option(
        False,
        "--detail",
        "-v",
        help=(
            "Flag (no value): verbose footer — full auth-mix lines, promo/overage "
            "scenarios, Heavy break-even, long caveats"
        ),
    ),
    app: list[str] | None = typer.Option(  # noqa: B008
        None,
        "--app",
        metavar="NAME",
        help="Requires substring: filter by app/project (repeatable, e.g. --app VCI)",
    ),
    json_out: bool = typer.Option(False, "--json", help="Flag (no value): machine-readable JSON"),
    include_unlabeled: bool = typer.Option(
        False,
        "--include-unlabeled",
        help=(
            "Flag (no value): with --by pr, also show sessions that never created a PR "
            "(keyed by session id). Default omit."
        ),
    ),
) -> None:
    """Token-accurate cost: list$ (API list rates) + est$ (path/regime spend lens).

    Options that take a value need the number/date on the same flag
    (e.g. --invoice-usd 180, not bare --invoice-usd). Use: grok-utils usage cost --help

    list$ = Build costUsdTicks ÷ 1e10 (same $ as /usage Session Cost).
            Pass -m MODEL to reconstruct from a published rate table instead.
    est$  = list$ × path/regime scale (API≈1.0; SuperGrok pool≈0; overage≈1.9)
            via auth timeline mix unless --cash-scale / prepaid-fit forces one scale.
    Footer: Wallet / auth snapshot (Extra Credits · weekly % · path) + weekly pool resets line. FAQ: usage info

      # Closed window
      grok-utils usage cost --from 2026-08-01 --to 2026-08-05 --by app

      # Per Grok Build session (PR labels when create_pull_request or gh pr create ran)
      grok-utils usage cost --from 2026-08-01 --by session

      # Per GitHub PR when the session created exactly one; multi-PR sessions stay one row
      grok-utils usage cost --from 2026-08-01 --by pr

      # From a date through latest session data (omit --to)
      grok-utils usage cost --from 2026-08-01 --by app

      # Plan advisor: API vs SuperGrok vs Heavy for the window
      grok-utils usage cost --from 2026-07-18 --by app --plan-advisor

      # One-shot wallet fit for a window (both amounts required)
      grok-utils usage cost ... --prepaid-usd 70 --credits-remaining 21.40

      # Model promo card cost (−25% or free tops) for est_cash$ / plan-advisor
      grok-utils usage cost ... -P --topoff-discount 0.25
      grok-utils usage cost ... -P --topoff-discount 1.0

      # Invoice allocation (amount required)
      grok-utils usage cost ... --invoice-usd 180 --fixed-usd 30

    PR-level Keys and clean session labels appear only when the Grok Build
    session reports them. If you skip this, you still get --by app (the
    repo inferred from cwd).

    One Grok Build session per unit of work. Several PRs from one parent chat
    stay one unsplit --by pr row. Keys with several PRs are one session;
    tokens are not split.

    Session cwd is the repo (or Grok worktree / repo-issue-N clone) for that
    work. Not an unrelated folder. --by app is the repo inferred from cwd.
    Issue worktrees and Grok worktrees roll into that repo Key. A chat
    started in the wrong repo shows that folder's name. PR labels, if any,
    come from whatever create_pull_request or gh pr create ran.

    PR labels: only github create_pull_request OkayOutput (number, html_url)
    or gh pr create stdout URL in updates.jsonl. Chat text and
    get_pull_request do not count. Fixes or Closes in the create body
    puts the issue number in the Key.

    --by pr lists every created PR. Unlabeled --by session Keys still
    pretty-print repo-issue-N clones as repo#N.

    See: grok-utils usage info
    """

    grok_home = get_grok_home(ctx.obj.get("grok_home") if ctx.obj else None)
    date_tz, date_tz_label = _resolve_date_tz(grok_home, tz)

    if mode == "rough":
        print_cost_rough(
            ctx,
            since=since or date_from,
            by=by if by in ("model", "project") else "model",
            top=top,
            show_all=show_all,
            json_out=json_out,
        )
        return

    if by not in COST_GROUPS:
        warn(f"Unknown --by {by}; using app")
        by = "app"
    if include_unlabeled and by != "pr":
        warn("--include-unlabeled only applies to --by pr; ignoring")
        include_unlabeled = False

    records, d_from, d_to, data_earliest, data_latest, prs_by_session = _load_filtered_usage(
        grok_home, since=since, date_from=date_from, date_to=date_to, apps=app, tz=date_tz
    )
    had_turns = bool(records)
    records = _records_for_group(records, by, prs_by_session, include_unlabeled=include_unlabeled)

    if not records:
        if by == "pr" and had_turns:
            warn(
                "No created PRs in this window (no github create_pull_request / "
                "gh pr create). Try --by session or --include-unlabeled."
            )
        else:
            warn("No turn usage records (no turn_completed usage in updates.jsonl).")
            warn("Tip: try --mode rough for legacy summary-based estimate, or check --from/--to.")
        return

    result_earliest, result_latest = _data_date_span(records, date_tz)
    win = build_token_cost_window(
        grok_home,
        records,
        group=by,
        rates_model=rates_model,
        cash_scale=cash_scale,
        prepaid_usd=prepaid_usd,
        credits_remaining=credits_remaining,
        topoff_discount=topoff_discount,
        d_from=d_from,
        d_to=d_to,
        data_earliest=data_earliest,
        data_latest=data_latest,
        result_earliest=result_earliest,
        result_latest=result_latest,
        prs_by_session=prs_by_session,
        include_unlabeled=include_unlabeled,
        date_tz=date_tz,
    )
    rates = win.rates
    rates_label = win.rates_label
    list_total = win.list_total
    est_total = win.est_total
    est_cash_total = win.est_cash_total
    tot = win.tot
    buckets = win.buckets
    shown_n = shown_bucket_count(len(buckets), top, show_all)
    shown_buckets = buckets[:shown_n]
    cut = bucket_cut_caption(shown_n, len(buckets))
    mix = win.mix
    cash_scale_val = win.cash_scale_val
    cash_scale_src = win.cash_scale_src
    force_uniform = win.force_uniform
    topoff_d = win.topoff_d
    topoff_src = win.topoff_src
    auth_st = win.auth_st
    weekly_pct = win.weekly_pct
    prepaid_balance = win.prepaid_balance
    usage_cfg = win.usage_cfg
    topoff_scenarios = resolve_topoff_discount_scenarios(
        usage_cfg, active_discount=topoff_d if topoff_d > 0 else None
    )

    scale_api, advisor_est = api_scale_for_advisor(win)
    advisor = None
    if plan_advisor_flag:
        if result_earliest is None or result_latest is None:
            warn("Plan advisor needs dated turns; skipping.")
        else:
            window_days = (result_latest - result_earliest).days + 1
            pa_cfg = load_plan_advisor_config(usage_cfg)
            advisor = plan_advisor(
                list_usd=list_total,
                est_usd=advisor_est,
                tokens=tot.total,
                cache_pct=tot.cache_pct,
                cash_scale=scale_api,
                window_days=window_days,
                project_days=int(pa_cfg["project_days"]),
                supergrok_usd=pa_cfg["supergrok_usd"],
                heavy_usd=pa_cfg["heavy_usd"],
                supergrok_weekly_include_usd=pa_cfg["supergrok_weekly_include_usd"],
                heavy_weekly_include_usd=pa_cfg["heavy_weekly_include_usd"],
            )

    inv_scale = 0.0
    fixed_per = 0.0
    show_invoice = invoice_usd is not None
    if show_invoice:
        if tot.ticks <= 0:
            warn("No costUsdTicks in data; cannot allocate --invoice-usd.")
            show_invoice = False
        else:
            inv_scale, fixed_per = allocate_invoice(
                buckets,
                invoice_usd=float(invoice_usd),  # type: ignore[arg-type]
                fixed_usd=fixed_usd,
                group=by,
                date_from=d_from,
                date_to=d_to,
            )

    if json_out:
        import json

        top_rows = []
        for b in shown_buckets:
            list_b = win.list_for_key(b.key)
            row = b.to_dict(rates)
            row["list_usd"] = round(list_b, 4)
            row["est_usd"] = round(win.est_for_key(b.key), 4)
            # Per-app regime list$ shares (reconciled %)
            path_map = mix.list_by_key_path.get(b.key) or {}
            if path_map:
                names = list(path_map.keys())
                weights = [path_map[n] for n in names]
                from ..utils.usage_display import _reconcile_pcts

                pcts = _reconcile_pcts(weights)
                row["regime_list_pct"] = {n: p for n, p in zip(names, pcts, strict=True) if p > 0}
                row["regime_list_usd"] = {n: round(path_map[n], 4) for n in names}
            if show_invoice:
                var = b.ticks * inv_scale
                row["variable_usd"] = round(var, 4)
                row["total_usd"] = round(var + fixed_per, 4)
            if list_price:
                row["list_price_usd"] = round(list_price_usd(b.ticks), 4)
            prs = _prs_for_bucket(b.key, by, prs_by_session)
            if prs:
                row["prs"] = prs
            top_rows.append(row)

        weeks = week_list_series(records, rates, prefer_ticks=win.prefer_ticks, tz=date_tz)
        pack_usd = resolve_topoff_pack_usd(usage_cfg)
        ov_scale = cfg_overage_scale(usage_cfg)
        plan_export = None
        if advisor is not None:
            plan_export = plan_advisor_export(
                advisor,
                topoff_scenarios=topoff_scenarios,
                active_topoff_discount=topoff_d,
                pack_usd=pack_usd,
                overage_scale=ov_scale,
                week_list=weeks,
                list_by_key_path=dict(mix.list_by_key_path),
                current_tier=win.subscription_tier,
                window_tiers=list(win.window_tiers),
            )

        payload = {
            "mode": "tokens",
            "by": by,
            "from": d_from.isoformat() if d_from else None,
            "to": d_to.isoformat() if d_to else None,
            "date_tz": date_tz_label,
            "data_earliest": data_earliest.isoformat() if data_earliest else None,
            "data_latest": data_latest.isoformat() if data_latest else None,
            "result_from": result_earliest.isoformat() if result_earliest else None,
            "result_to": result_latest.isoformat() if result_latest else None,
            "rates_model": rates_label,
            "list_source": win.list_source,
            "rates": rates.as_dict(),
            "cash_scale": cash_scale_val,
            "cash_scale_source": cash_scale_src,
            "topoff_discount": topoff_d,
            "topoff_discount_source": topoff_src,
            "topoff_pack_usd": pack_usd,
            "effective_rates": (
                effective_rates(rates, cash_scale_val).as_dict()
                if force_uniform is not None and cash_scale_val > 0
                else None
            ),
            "auth": auth_st.as_dict(),
            "wallet": {
                "extra_credits_remaining_usd": prepaid_balance,
                "weekly_supergrok_limit_pct_used": weekly_pct,
                "weekly_limit_pct_used": weekly_pct,
                "weekly_period_start": iso_or_none(win.weekly_period_start),
                "weekly_resets_at": iso_or_none(win.weekly_period_end),
                "subscription_tier": win.subscription_tier,
                "subscription_tier_raw": win.subscription_tier_raw,
                "subscription_tier_label": (
                    "Heavy"
                    if win.subscription_tier == "heavy"
                    else ("SuperGrok" if win.subscription_tier == "supergrok" else None)
                ),
                "auth_path": auth_st.effective,
            },
            "weekly_usage_pct": weekly_pct,
            "weekly_resets_at": iso_or_none(win.weekly_period_end),
            "subscription_tier": win.subscription_tier,
            "prepaid_balance_usd": prepaid_balance,
            "topoff_discount_scenarios": topoff_scenarios,
            "auth_mix": mix.as_dict(),
            "week_list_usd": [{"week": w, "list_usd": round(u, 4)} for w, u in weeks],
            "totals": {
                **tot.to_dict(rates),
                "list_usd": round(list_total, 4),
                "api_est_usd": round(list_total, 4),
                "est_usd": round(est_total, 4),
                "est_cash_usd": round(est_cash_total, 4),
                "list_price_usd": round(list_price_usd(tot.ticks), 4) if list_price else None,
            },
            "invoice": (
                {
                    "invoice_usd": invoice_usd,
                    "fixed_usd": fixed_usd,
                    "scale_per_tick": inv_scale,
                    "fixed_per_bucket": fixed_per,
                }
                if show_invoice
                else None
            ),
            "buckets": top_rows,
            "plan_advisor": plan_export
            if plan_export
            else (advisor.as_dict() if advisor else None),
            "caveats": [
                "list$_is_costUsdTicks_div_1e10_when_present_else_rates",
                "est$_uses_auth_timeline_mix_unless_uniform_override",
                "weekly_pct_unknown_uses_list_scale_not_pool_or_overage",
                "subscription_tier_from_billing_log_not_session_turns",
                "plan_advisor_pure_api_uses_api_scale_not_table_scale",
                "topoff_discount_is_card_promo_not_list$",
                "pass_-m_to_force_reconstructed_rate_table",
                "session_prs_from_create_pull_request_or_gh_pr_create_only",
                "pr_group_is_1to1_or_unsplit_multi",
            ],
        }
        print(json.dumps(payload, indent=2))
        return

    period = ""
    if result_earliest or result_latest or d_from or d_to:
        left = (
            result_earliest.isoformat()
            if result_earliest
            else (d_from.isoformat() if d_from else "…")
        )
        right = result_latest.isoformat() if result_latest else (d_to.isoformat() if d_to else "…")
        period = f" · {left} → {right}"
        if d_from is not None and result_earliest is not None and d_from < result_earliest:
            period += f"  (requested --from {d_from.isoformat()})"
    headers = ["Key", "Prm", "Tokens", "Cache%", "list$", "est$"]
    if show_invoice:
        headers += ["var$", "tot$"]
    if list_price:
        headers.append("ticks$")
    headers.append("Share(list$)")

    t = make_table(
        f"Estimated Cost by {by} (list$ primary · est$=path scale, {cut}){period}",
        headers,
        no_wrap=("Key",),
    )
    row_keys = _row_display_keys(
        [b.key for b in shown_buckets],
        by,
        prs_by_session,
        records,
    )
    share_vals = [win.list_for_key(b.key) for b in shown_buckets]
    max_share = max(share_vals, default=1.0) or 1.0
    for b, key in zip(shown_buckets, row_keys, strict=True):
        list_b = win.list_for_key(b.key)
        est_b = win.est_for_key(b.key)
        cells: list[str] = [
            key,
            str(b.n),
            _fmt_tokens(b.total),
            f"{b.cache_pct:.1f}%",
            f"{list_b:.2f}",
            f"{est_b:.2f}",
        ]
        if show_invoice:
            var = b.ticks * inv_scale
            cells.extend([f"{var:.2f}", f"{var + fixed_per:.2f}"])
        if list_price:
            cells.append(f"{list_price_usd(b.ticks):.2f}")
        cells.append(_ascii_bar(list_b, max_share, 12))
        t.add_row(*cells)
    console.print(t)
    print_bucket_cut_note(shown_n, len(buckets))
    _maybe_print_unsplit_pr_note(by, [b.key for b in shown_buckets], prs_by_session)

    print_token_cost_summary(win, detail=detail, cost_mode=True, show_faq_hint=False)
    if show_invoice:
        console.print(
            f"  Invoice allocation: ${_invoice_total(invoice_usd, fixed_usd):.2f} "
            f"(var by ticks + fixed amortized) — relative only"
        )
    if list_price:
        console.print(
            f"  costUsdTicks÷1e10: ${list_price_usd(tot.ticks):,.4f}  "
            f"[dim](same unit as /usage Session Cost)[/dim]"
        )

    if api_estimate:
        print_api_breakdown(tot, rates, rates_label)

    if advisor is not None:
        print_plan_advisor(
            advisor,
            auth_line=format_auth_plan_advisor_line(
                auth_st, subscription_tier=win.subscription_tier
            ),
            overage_scale=cfg_overage_scale(usage_cfg),
            topoff_scenarios=topoff_scenarios,
            active_topoff_discount=topoff_d,
            detail=detail,
            mix_slices=list(mix.slices),
            pack_usd=resolve_topoff_pack_usd(usage_cfg),
            week_list=week_list_series(records, rates, tz=date_tz),
            list_by_key_path=dict(mix.list_by_key_path),
            current_tier=win.subscription_tier,
            window_tiers=list(win.window_tiers),
        )

    if detail:
        console.print(
            "\n[dim]FAQ / ledgers: grok-utils usage info"
            "  ·  wallet + history: grok-utils auth status [--history]"
            "  ·  tune: --cash-scale / --topoff-discount / toml[/dim]"
        )
    else:
        console.print(
            "\n[dim]FAQ: grok-utils usage info"
            "  ·  more: --detail / -v"
            "  ·  wallet: grok-utils auth status[/dim]"
        )


def _invoice_total(invoice_usd: float | None, fixed_usd: float) -> float:
    return float(invoice_usd or 0) + float(fixed_usd or 0)
