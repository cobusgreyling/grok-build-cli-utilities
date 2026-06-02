"""Main Typer CLI for grok-utils. Registers all subcommands."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

from . import __version__
from .commands import (
    backup,
    doctor,
    mcp,
    memory,
    sessions,
    skills,
    usage,
    worktree,
)

app = typer.Typer(
    name="grok-utils",
    help="""Amazing Grok Build CLI Utilities.

A curated set of power tools for Grok Build users.
Manage sessions, skills, backups, usage analytics, MCP, worktrees, memory and diagnostics
with beautiful output and safe operations.

Author: Cobus Greyling
""",
    add_completion=True,
    rich_markup_mode="rich",
    no_args_is_help=True,
)

console = Console()


def version_callback(value: bool) -> None:
    if value:
        console.print(f"grok-utils [bold cyan]{__version__}[/bold cyan]")
        console.print("Author: [bold]Cobus Greyling[/bold]")
        console.print("https://github.com/cobusgreyling/grok-build-cli-utilities")
        raise typer.Exit()


@app.callback()
def main(
    ctx: typer.Context,
    grok_home: Optional[Path] = typer.Option(
        None,
        "--grok-home",
        "-g",
        envvar="GROK_HOME",
        help="Path to .grok directory (default: ~/.grok)",
        exists=False,
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
    ),
    version: bool = typer.Option(
        None,
        "--version",
        "-v",
        callback=version_callback,
        is_eager=True,
        help="Show version and exit",
    ),
) -> None:
    """grok-utils - power tools for Grok Build by Cobus Greyling."""
    # Store in context so commands can access
    ctx.obj = {"grok_home": grok_home}


# Register subcommands
app.add_typer(
    sessions.app, name="sessions", help="Advanced session browser, search, stats and pruning"
)
app.add_typer(skills.app, name="skills", help="Skill discovery, creation, validation and packaging")
app.add_typer(
    backup.app, name="backup", help="Safe, selective backup and restore for your entire Grok state"
)
app.add_typer(usage.app, name="usage", help="Beautiful usage analytics, reports and trends")
app.add_typer(mcp.app, name="mcp", help="MCP server inspection, testing and config helpers")
app.add_typer(worktree.app, name="worktree", help="Git worktree + Grok session hygiene tools")
app.add_typer(
    memory.app, name="memory", help="Cross-session memory explorer and curator (experimental)"
)

# Top-level convenience commands (not a subcommand group)
app.command("doctor", help="Diagnose your Grok Build environment and grok-utils setup")(
    doctor.doctor
)


if __name__ == "__main__":
    app()
