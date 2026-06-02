"""grok-utils logs - lightweight query over unified.jsonl (no heavy indexing)."""

from __future__ import annotations

from typing import Optional

import typer

from ..utils.common import (
    console,
    get_grok_home,
    make_table,
    warn,
)
from ..utils.parsers import tail_logs

app = typer.Typer(
    help="Tail and query the Grok unified log (quick diagnostics)", no_args_is_help=True
)


@app.command("tail")
def logs_tail(
    ctx: typer.Context,
    n: int = typer.Option(30, "--lines", "-n"),
    level: Optional[str] = typer.Option(None, "--level", "-l", help="error | info | warn"),
    json_out: bool = typer.Option(False, "--json"),
) -> None:
    """Show the last N log lines (optionally filtered by level)."""
    grok_home = get_grok_home(ctx.obj.get("grok_home") if ctx.obj else None)
    lines = tail_logs(grok_home, lines=n, level=level)

    if not lines:
        warn("No logs or log file missing.")
        return

    if json_out:
        import json

        console.print(json.dumps(lines, indent=2))
        return

    t = make_table(f"Logs (last {len(lines)})", ["Time", "Src", "Lvl", "Message"])
    for d in lines[-n:]:
        ts = str(d.get("ts", ""))[-19:]
        src = str(d.get("src", ""))[:12]
        lvl = str(d.get("lvl", ""))[:6]
        msg = str(d.get("msg", ""))[:70]
        t.add_row(ts, src, lvl, msg)
    console.print(t)
