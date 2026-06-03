"""grok-utils sessions - advanced session management."""

from __future__ import annotations

import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import typer
from rich.progress import Progress
from rich.table import Table

from ..utils.common import (
    console,
    count_tool_calls,
    error,
    format_age,
    format_dt,
    get_grok_home,
    get_sqlite_search_db,
    info as ui_info,
    iter_sessions,
    load_session_updates,
    make_table,
    Panel,
    parse_age_delta,
    search_sessions_sqlite,
    success,
    warn,
)
from ..utils.parsers import (
    load_rewind_points,
    load_session_signals,
)

app = typer.Typer(help="Powerful Grok Build session tools", no_args_is_help=True)


@app.command("list")
def list_sessions(
    ctx: typer.Context,
    limit: int = typer.Option(30, "--limit", "-l", help="Max sessions to show"),
    project: Optional[str] = typer.Option(
        None, "--project", "-p", help="Filter by substring in cwd"
    ),
    model: Optional[str] = typer.Option(None, "--model", "-m", help="Filter by current model"),
    since: Optional[str] = typer.Option(None, "--since", help="ISO date, e.g. 2026-05-01"),
    json_out: bool = typer.Option(False, "--json", help="Output JSON for scripting"),
) -> None:
    """List recent sessions with rich filters."""
    grok_home = get_grok_home(ctx.obj.get("grok_home") if ctx.obj else None)

    with Progress() as prog:
        sessions = list(iter_sessions(grok_home, prog))

    # filters
    if project:
        sessions = [s for s in sessions if project.lower() in s.cwd.lower()]
    if model:
        sessions = [s for s in sessions if model.lower() in s.current_model_id.lower()]
    if since:
        try:
            cutoff = datetime.fromisoformat(since).replace(tzinfo=timezone.utc)
            sessions = [s for s in sessions if s.created_at and s.created_at >= cutoff]
        except (ValueError, TypeError, OverflowError):
            error(f"Bad --since date: {since}")
            raise typer.Exit(1)

    sessions.sort(
        key=lambda s: s.last_active_at or s.created_at or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )
    sessions = sessions[:limit]

    if json_out:
        import json as _json

        data = [
            {
                "id": s.id,
                "cwd": s.cwd,
                "created": s.created_at.isoformat() if s.created_at else None,
                "updated": s.updated_at.isoformat() if s.updated_at else None,
                "messages": s.num_messages,
                "model": s.current_model_id,
                "agent": s.agent_name,
            }
            for s in sessions
        ]
        console.print(_json.dumps(data, indent=2))
        return

    if not sessions:
        warn("No sessions found matching filters.")
        return

    t = make_table(
        f"Sessions ({len(sessions)} shown)",
        ["ID (short)", "Project / CWD", "Last Active", "Msgs", "Model", "Agent"],
    )
    for s in sessions:
        short_id = s.id[:8] + "…"
        proj = s.cwd
        if len(proj) > 42:
            proj = "…" + proj[-41:]
        t.add_row(
            short_id,
            proj,
            format_age(s.last_active_at),
            str(s.num_messages),
            s.current_model_id,
            s.agent_name[:18] if s.agent_name else "",
        )
    console.print(t)
    console.print(
        f"\n[dim]Total scanned: {len(list(iter_sessions(grok_home)))} • Use [bold]grok-utils sessions info <id>[/bold] for details[/dim]"
    )


@app.command("search")
def search(
    ctx: typer.Context,
    query: str = typer.Argument(..., help="Search term (uses session FTS sqlite when available)"),
    limit: int = typer.Option(20, "--limit", "-l"),
) -> None:
    """Full-text search across session transcripts (best effort)."""
    grok_home = get_grok_home(ctx.obj.get("grok_home") if ctx.obj else None)
    db = get_sqlite_search_db(grok_home)

    results = []
    if db:
        results = search_sessions_sqlite(db, query, limit)
        if results:
            console.print(
                f"[dim]Using built-in session_search.sqlite FTS ({len(results)} hits)[/dim]"
            )

    if not results:
        # fallback: scan summaries + a bit of content
        warn("No FTS index or no hits; falling back to summary scan (slower).")
        with Progress() as prog:
            all_s = list(iter_sessions(grok_home, prog))
        q = query.lower()
        for s in all_s:
            if (
                q in (s.summary_text or "").lower()
                or q in s.cwd.lower()
                or q in s.agent_name.lower()
            ):
                results.append({"id": s.id, "cwd": s.cwd, "snippet": (s.summary_text or "")[:160]})
            if len(results) >= limit:
                break

    if not results:
        warn(f"No matches for '{query}'")
        return

    t = make_table(f"Search: {query}", ["ID", "CWD", "Snippet / Match"])
    for r in results[:limit]:
        sid = r.get("id") or r.get("session_id", "—")[:12]
        cwd = r.get("cwd", r.get("path", "—"))
        snip = r.get("snippet", r.get("content", ""))[:120].replace("\n", " ")
        t.add_row(sid, str(cwd)[:45], snip)
    console.print(t)


@app.command("info")
def info(
    ctx: typer.Context,
    session_id: str = typer.Argument(..., help="Full or prefix session ID"),
    deep: bool = typer.Option(False, "--deep", help="Parse updates.jsonl for tool stats (slower)"),
) -> None:
    """Show detailed info for one session."""
    grok_home = get_grok_home(ctx.obj.get("grok_home") if ctx.obj else None)
    with Progress() as prog:
        sessions = list(iter_sessions(grok_home, prog))

    matches = [s for s in sessions if s.id.startswith(session_id) or s.id.endswith(session_id)]
    if not matches:
        error(f"No session matching {session_id}")
        raise typer.Exit(1)
    if len(matches) > 1:
        warn(f"Multiple matches, using most recent: {matches[0].id}")
    s = matches[0]

    console.print(
        Panel.fit(
            f"[bold]{s.id}[/bold]\n"
            f"CWD: [cyan]{s.cwd}[/cyan]\n"
            f"Created: {format_dt(s.created_at)} ({format_age(s.created_at)})\n"
            f"Last active: {format_dt(s.last_active_at)}\n"
            f"Messages: {s.num_messages} (chat: {s.num_chat_messages})\n"
            f"Model: [green]{s.current_model_id}[/green]   Agent: {s.agent_name or 'default'}",
            title="Session Details",
            border_style="cyan",
        )
    )

    if deep:
        console.print("[dim]Loading updates for tool stats...[/dim]")
        updates = load_session_updates(s.path, limit=5000)
        tools = count_tool_calls(updates)
        if tools:
            t = Table(title="Tool Usage (sampled)", show_header=False)
            for name, cnt in sorted(tools.items(), key=lambda x: -x[1])[:12]:
                t.add_row(name, str(cnt))
            console.print(t)
        else:
            ui_info("No tool_call events found in first 5k updates (or very short session).")


@app.command("stats")
def stats(ctx: typer.Context) -> None:
    """Quick aggregate stats over all sessions."""
    grok_home = get_grok_home(ctx.obj.get("grok_home") if ctx.obj else None)
    with Progress() as prog:
        sessions = list(iter_sessions(grok_home, prog))

    if not sessions:
        warn("No sessions.")
        return

    total_msgs = sum(s.num_messages for s in sessions)
    models: dict[str, int] = {}
    projects: dict[str, int] = {}
    createds: list[datetime] = [s.created_at for s in sessions if s.created_at]
    oldest = min(createds) if createds else None
    actives: list[datetime] = []
    for s in sessions:
        dt = s.last_active_at or s.created_at
        if dt:
            actives.append(dt)
    newest = max(actives) if actives else None

    for s in sessions:
        models[s.current_model_id] = models.get(s.current_model_id, 0) + 1
        proj = s.cwd
        projects[proj] = projects.get(proj, 0) + 1

    top_models = sorted(models.items(), key=lambda x: -x[1])[:5]
    top_projects = sorted(projects.items(), key=lambda x: -x[1])[:5]

    console.print(
        Panel(
            f"Sessions: [bold]{len(sessions)}[/bold]\n"
            f"Total messages: [bold]{total_msgs}[/bold]\n"
            f"Date range: {format_dt(oldest)} → {format_dt(newest)}\n\n"
            f"Top models:\n" + "\n".join(f"  • {m}: {c}" for m, c in top_models) + "\n\n"
            "Top projects:\n" + "\n".join(f"  • {p[:55]}: {c}" for p, c in top_projects),
            title="Session Statistics",
            border_style="green",
        )
    )


@app.command("prune")
def prune(
    ctx: typer.Context,
    older_than: str = typer.Option("90d", "--older-than", help="e.g. 30d, 2w, 6mo, 1y, 48h"),
    project: Optional[str] = typer.Option(None, "--project"),
    dry_run: bool = typer.Option(
        True, "--dry-run/--no-dry-run", help="Default safe: only show what would be deleted"
    ),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation"),
) -> None:
    """Prune old sessions (DANGEROUS - defaults to dry-run)."""
    grok_home = get_grok_home(ctx.obj.get("grok_home") if ctx.obj else None)

    delta = parse_age_delta(older_than)
    cutoff = datetime.now(timezone.utc) - delta

    with Progress() as prog:
        sessions = list(iter_sessions(grok_home, prog))

    victims = []
    for s in sessions:
        act = s.last_active_at or s.created_at
        if act and act < cutoff:
            if project and project.lower() not in s.cwd.lower():
                continue
            victims.append(s)

    if not victims:
        success("Nothing to prune.")
        return

    console.print(f"[yellow]Would prune {len(victims)} sessions older than {older_than}[/yellow]")
    for v in victims[:8]:
        console.print(f"  {v.id[:8]}  {format_age(v.last_active_at)}  {v.cwd[:50]}")
    if len(victims) > 8:
        console.print(f"  ... and {len(victims) - 8} more")

    if dry_run:
        console.print(
            "[bold yellow]DRY RUN[/bold yellow] — nothing deleted. Re-run with --no-dry-run to actually delete."
        )
        return

    if not yes and not typer.confirm(
        f"Really DELETE {len(victims)} session directories? This is irreversible.", default=False
    ):
        error("Aborted.")
        raise typer.Exit(1)

    import shutil

    deleted = 0
    for v in victims:
        try:
            shutil.rmtree(v.path)
            deleted += 1
        except Exception as e:
            warn(f"Failed to delete {v.id}: {e}")
    success(f"Deleted {deleted} session(s).")


@app.command("analyze")
def analyze(
    ctx: typer.Context,
    session_id: str = typer.Argument(..., help="Session ID prefix or full"),
    json_out: bool = typer.Option(False, "--json"),
) -> None:
    """Deep analysis of a session using signals.json + rewind points + tool counts."""
    grok_home = get_grok_home(ctx.obj.get("grok_home") if ctx.obj else None)
    with Progress() as prog:
        sessions = list(iter_sessions(grok_home, prog))

    matches = [s for s in sessions if s.id.startswith(session_id) or s.id.endswith(session_id)]
    if not matches:
        error(f"No match for {session_id}")
        raise typer.Exit(1)
    s = matches[0]

    sig = load_session_signals(s.path)
    rewinds = load_rewind_points(s.path, limit=5)
    updates = load_session_updates(s.path, limit=2000)
    tools = count_tool_calls(updates)

    if json_out:
        import json

        console.print(
            json.dumps(
                {
                    "id": s.id,
                    "signals": sig.raw if sig else None,
                    "rewind_points_sample": len(rewinds),
                    "tool_counts_sample": tools,
                },
                indent=2,
            )
        )
        return

    console.print(Panel.fit(f"[bold]{s.id}[/bold]\nCWD: {s.cwd}", title="Session"))

    if sig:
        console.print(
            f"Turns: {sig.turn_count}  Tool calls: {sig.tool_call_count}  Errors: {sig.error_count}\n"
            f"Compactions: {sig.compaction_count}  Tokens used: {sig.context_tokens_used}/{sig.context_window_tokens}\n"
            f"Duration: {sig.session_duration_s}s  Files touched (agent): {sig.agent_files_touched}\n"
            f"Tools: {', '.join(sig.tools_used[:8])}{'…' if len(sig.tools_used) > 8 else ''}"
        )
    else:
        ui_info("No signals.json (older session or not fully captured).")

    if rewinds:
        console.print(
            f"\nRewind points available: {len(rewinds)} (latest prompt_index ~{rewinds[-1].prompt_index})"
        )
    if tools:
        t = Table(title="Recent tool usage sample", show_header=False)
        for nm, cnt in sorted(tools.items(), key=lambda x: -x[1])[:8]:
            t.add_row(nm, str(cnt))
        console.print(t)


@app.command("export")
def export_session(
    ctx: typer.Context,
    session_id: str = typer.Argument(..., help="Session ID (prefix ok)"),
    fmt: str = typer.Option("md", "--format", "-f", help="md | html | json"),
    out: Optional[str] = typer.Option(None, "--out", "-o", help="Write to file instead of stdout"),
    json_out: bool = typer.Option(False, "--json", help="When fmt=json this is implied"),
) -> None:
    """Export a session transcript/summary to markdown, simple HTML or JSON.
    Includes summary, signals, tool stats and basic rewind info.
    """
    grok_home = get_grok_home(ctx.obj.get("grok_home") if ctx.obj else None)
    with Progress() as prog:
        sessions = list(iter_sessions(grok_home, prog))

    matches = [s for s in sessions if s.id.startswith(session_id) or s.id.endswith(session_id)]
    if not matches:
        error(f"No session matching {session_id}")
        raise typer.Exit(1)
    s = matches[0]

    sig = load_session_signals(s.path)
    rew = load_rewind_points(s.path, 3)
    updates = load_session_updates(s.path, 1500)
    tools = count_tool_calls(updates)

    if fmt == "json" or json_out:
        import json

        data = {
            "id": s.id,
            "cwd": s.cwd,
            "created": s.created_at.isoformat() if s.created_at else None,
            "messages": s.num_messages,
            "model": s.current_model_id,
            "signals": sig.raw if sig else None,
            "tool_counts": tools,
            "rewind_points": len(rew),
        }
        content = json.dumps(data, indent=2)
    elif fmt == "html":
        content = f"""<!doctype html>
<html><head><meta charset="utf-8"><title>Session {s.id}</title>
<style>body{{font-family:sans-serif;margin:2rem}} pre{{background:#f6f6f6;padding:1rem}}</style></head>
<body>
<h1>Session {s.id}</h1>
<p><b>CWD:</b> {s.cwd} | <b>Model:</b> {s.current_model_id} | <b>Messages:</b> {s.num_messages}</p>
<h2>Signals</h2><pre>{(sig.raw if sig else {})}</pre>
<h2>Tool sample</h2><pre>{tools}</pre>
<h2>Rewinds</h2><p>{len(rew)} points captured</p>
</body></html>"""
    else:
        # md
        lines = [
            f"# Session {s.id}",
            "",
            f"- **CWD**: {s.cwd}",
            f"- **Created**: {format_dt(s.created_at)}",
            f"- **Messages**: {s.num_messages}",
            f"- **Model**: {s.current_model_id}",
            "",
        ]
        if sig:
            lines += [
                "## Signals",
                f"- Turns: {sig.turn_count}, Tool calls: {sig.tool_call_count}, Errors: {sig.error_count}",
                f"- Compactions: {sig.compaction_count}, Context: {sig.context_tokens_used}/{sig.context_window_tokens}",
                f"- Tools used: {', '.join(sig.tools_used[:10])}",
                "",
            ]
        if tools:
            lines += ["## Tools (sampled)", ""]
            for nm, c in sorted(tools.items(), key=lambda x: -x[1])[:10]:
                lines.append(f"- {nm}: {c}")
            lines.append("")
        if rew:
            lines += [f"## Rewind points: {len(rew)} (preview of last few)", ""]
        content = "\n".join(lines)

    if out:
        Path(out).write_text(content, encoding="utf-8")
        success(f"Wrote {fmt} export to {out}")
    else:
        console.print(content)


@app.command("resume")
def resume(
    ctx: typer.Context,
    session_id: Optional[str] = typer.Argument(
        None, help="Full or prefix session ID (omitted = most recent for CWD)"
    ),
    json_out: bool = typer.Option(
        False, "--json", help="Print the launch command as JSON (no exec)"
    ),
) -> None:
    """Resume a session by delegating to the real `grok --resume` (finds full ID)."""
    grok_home = get_grok_home(ctx.obj.get("grok_home") if ctx.obj else None)

    with Progress() as prog:
        sessions = list(iter_sessions(grok_home, prog))

    if not sessions:
        error("No sessions found.")
        raise typer.Exit(1)

    if session_id:
        matches = [s for s in sessions if s.id.startswith(session_id) or s.id.endswith(session_id)]
        if not matches:
            error(f"No session matching '{session_id}'")
            raise typer.Exit(1)
        if len(matches) > 1:
            # prefer most recent
            matches.sort(
                key=lambda s: (
                    s.last_active_at or s.created_at or datetime.min.replace(tzinfo=timezone.utc)
                ),
                reverse=True,
            )
            warn(f"Multiple matches for prefix, using most recent: {matches[0].id[:12]}…")
        target = matches[0]
    else:
        # Prefer sessions in current working dir, fall back to global most recent
        cwd = str(Path.cwd().resolve())
        same_cwd = [s for s in sessions if str(Path(s.cwd).resolve()) == cwd]
        pool = same_cwd if same_cwd else sessions
        target = max(
            pool,
            key=lambda s: (
                s.last_active_at or s.created_at or datetime.min.replace(tzinfo=timezone.utc)
            ),
        )
        ui_info(f"Resuming most recent session: {target.id[:12]}… in {target.cwd}")

    grok_bin = grok_home / "bin" / "grok"
    if grok_bin.exists():
        cmd = [str(grok_bin), "--resume", target.id]
    else:
        cmd = ["grok", "--resume", target.id]

    env = os.environ.copy()
    # ensure custom grok home is honored by child
    if grok_home != (Path.home() / ".grok"):
        env["GROK_HOME"] = str(grok_home)

    if json_out:
        import json as _json

        console.print(
            _json.dumps({"cmd": cmd, "session_id": target.id, "cwd": target.cwd}, indent=2)
        )
        return

    console.print(f"[dim]→ {' '.join(cmd)}[/dim]")
    try:
        # Replace current process (clean terminal takeover for the TUI)
        os.execvpe(cmd[0], cmd, env)
    except FileNotFoundError:
        warn(f"'{cmd[0]}' not found in PATH or at {grok_bin}. Falling back to subprocess.")
        # Fallback: run and wait (works but may have slight terminal differences)
        res = subprocess.run(cmd, env=env)
        raise typer.Exit(res.returncode)
    except Exception as e:
        error(f"Failed to launch grok: {e}")
        ui_info(f"You can run manually: {' '.join(cmd)}")
        raise typer.Exit(1)
