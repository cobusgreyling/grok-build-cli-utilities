"""grok-utils plugins - rich discovery, inventory and validation for Grok plugins."""

from __future__ import annotations

import subprocess
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
from ..utils.parsers import (
    Plugin,
    iter_plugins,
    parse_plugin,
    validate_plugin,
)

app = typer.Typer(
    help="Plugin discovery, inventory, validation (richer than native grok plugin)",
    no_args_is_help=True,
)


@app.command("list")
def list_plugins(
    ctx: typer.Context,
    all: bool = typer.Option(False, "--all", "-a", help="Include marketplace cache sources"),
    json_out: bool = typer.Option(False, "--json"),
) -> None:
    """List discovered plugins with component summary (skills/agents/hooks/mcp)."""
    grok_home = get_grok_home(ctx.obj.get("grok_home") if ctx.obj else None)
    plugins = iter_plugins(grok_home, include_marketplace=all)

    if json_out:
        import json

        console.print(
            json.dumps(
                [
                    {
                        "name": p.name,
                        "scope": p.scope,
                        "version": p.version,
                        "description": p.description,
                        "components": p.components,
                        "path": str(p.path),
                    }
                    for p in plugins
                ],
                indent=2,
            )
        )
        return

    if not plugins:
        warn("No plugins discovered in user/project locations.")
        info("Install with `grok plugin install <source>` or add local dirs under .grok/plugins/")
        return

    t = make_table(f"Plugins ({len(plugins)})", ["Name", "Scope", "Ver", "Components", "Path"])
    for p in plugins:
        comp = ",".join(p.components) if p.components else "—"
        t.add_row(
            f"[bold cyan]{p.name}[/bold cyan]",
            p.scope,
            p.version or "—",
            comp,
            str(p.path.relative_to(Path.home()))
            if str(p.path).startswith(str(Path.home()))
            else str(p.path),
        )
    console.print(t)
    console.print(
        "\n[dim]Use `grok-utils plugins info <name>` or native `grok plugin list` for management.[/dim]"
    )


@app.command("info")
def plugin_info(
    ctx: typer.Context,
    name: str = typer.Argument(..., help="Plugin name (or path for local)"),
    json_out: bool = typer.Option(False, "--json"),
) -> None:
    """Show details for one plugin."""
    grok_home = get_grok_home(ctx.obj.get("grok_home") if ctx.obj else None)
    plugins = iter_plugins(grok_home, include_marketplace=True)

    matches = [p for p in plugins if p.name.lower() == name.lower() or str(p.path).endswith(name)]
    if not matches:
        # try direct path
        cand = Path(name)
        if cand.exists():
            matches = [parse_plugin(cand, scope="local") or Plugin(name=name, path=cand)]  # type: ignore
    if not matches:
        error(f"No plugin matching '{name}'")
        raise typer.Exit(1)

    p = matches[0]

    if json_out:
        import json

        console.print(
            json.dumps(
                {
                    "name": p.name,
                    "scope": p.scope,
                    "version": p.version,
                    "description": p.description,
                    "author": p.author,
                    "components": p.components,
                    "path": str(p.path),
                },
                indent=2,
            )
        )
        return

    console.print(f"[bold]{p.name}[/bold] ({p.scope})  v{p.version or '?'}")
    if p.description:
        console.print(f"  {p.description}")
    if p.author:
        console.print(f"  author: {p.author}")
    console.print(f"  path: {p.path}")
    console.print(f"  components: {', '.join(p.components) if p.components else 'none detected'}")

    # quick validation
    errs = validate_plugin(p)
    if errs:
        warn("Validation issues: " + "; ".join(errs))
    else:
        success("Looks valid (has components).")


@app.command("validate")
def validate(
    ctx: typer.Context,
    path: Optional[str] = typer.Argument(None, help="Path to plugin dir (default: scan all)"),
    json_out: bool = typer.Option(False, "--json"),
) -> None:
    """Validate one plugin or all discovered ones."""
    grok_home = get_grok_home(ctx.obj.get("grok_home") if ctx.obj else None)

    if path:
        p = parse_plugin(Path(path), scope="local")
        if not p:
            error("Path does not look like a plugin (no skills/agents/hooks etc).")
            raise typer.Exit(1)
        plugins = [p]
    else:
        plugins = iter_plugins(grok_home, include_marketplace=False)

    results = []
    for pl in plugins:
        errs = validate_plugin(pl)
        results.append(
            {"name": pl.name, "path": str(pl.path), "valid": len(errs) == 0, "errors": errs}
        )

    if json_out:
        import json

        console.print(json.dumps(results, indent=2))
        return

    t = make_table("Plugin Validation", ["Name", "Status", "Issues", "Path"])
    for r in results:
        status = "✓" if r["valid"] else "✗"
        raw_errs = r.get("errors") or []
        issue_list: list[str] = (
            [str(x) for x in raw_errs] if isinstance(raw_errs, (list, tuple)) else []
        )
        issues = "; ".join(issue_list)[:60] if issue_list else "ok"
        pth = str(r.get("path", ""))
        t.add_row(str(r.get("name", "")), status, issues, pth[:40])
    console.print(t)

    bad = [r for r in results if not r["valid"]]
    if bad:
        warn(f"{len(bad)} plugin(s) with issues.")
    else:
        success("All scanned plugins look good.")


@app.command("inventory")
def inventory(ctx: typer.Context, json_out: bool = typer.Option(False, "--json")) -> None:
    """Aggregate view: total skills/agents/hooks/MCP across all plugins."""
    grok_home = get_grok_home(ctx.obj.get("grok_home") if ctx.obj else None)
    plugins = iter_plugins(grok_home, include_marketplace=False)

    total_skills = sum(1 for p in plugins if p.has_skills)
    total_agents = sum(1 for p in plugins if p.has_agents)
    total_hooks = sum(1 for p in plugins if p.has_hooks)
    total_mcp = sum(1 for p in plugins if p.has_mcp)

    if json_out:
        import json

        console.print(
            json.dumps(
                {
                    "plugins": len(plugins),
                    "skills": total_skills,
                    "agents": total_agents,
                    "hooks": total_hooks,
                    "mcp": total_mcp,
                },
                indent=2,
            )
        )
        return

    console.print(
        f"[bold]Plugin Inventory[/bold]\n"
        f"  Plugins: {len(plugins)}\n"
        f"  Skills-bearing: {total_skills}\n"
        f"  Agents-bearing: {total_agents}\n"
        f"  Hooks-bearing: {total_hooks}\n"
        f"  MCP-bearing: {total_mcp}\n"
    )
    info(
        "Use `grok-utils skills list` to see the deduped effective skill set (plugins contribute to it)."
    )


# Optional delegation helper (can be called from doctor or elsewhere)
def _run_native_plugin_list(grok_home: Path) -> Optional[str]:
    grok_bin = grok_home / "bin" / "grok"
    if not grok_bin.exists():
        return None
    try:
        out = subprocess.run(
            [str(grok_bin), "plugin", "list"],
            capture_output=True,
            text=True,
            timeout=6,
        )
        if out.returncode == 0:
            return out.stdout.strip()
    except Exception:
        pass
    return None
