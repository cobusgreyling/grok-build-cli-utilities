"""grok-utils config - inspect effective Grok configuration safely."""

from __future__ import annotations


import typer

from ..utils.common import (
    console,
    get_grok_home,
    info,
    make_table,
    success,
    warn,
)
from ..utils.parsers import load_config

app = typer.Typer(
    help="View and validate your config.toml + related settings (read-only)", no_args_is_help=True
)


@app.command("show")
def show_config(
    ctx: typer.Context,
    effective: bool = typer.Option(
        True, "--effective/--raw", help="Show parsed sections (default)"
    ),
    json_out: bool = typer.Option(False, "--json"),
) -> None:
    """Pretty print config.toml (and a few other key settings files)."""
    grok_home = get_grok_home(ctx.obj.get("grok_home") if ctx.obj else None)
    cfg = load_config(grok_home)

    if json_out:
        import json

        out = {"config": cfg, "grok_home": str(grok_home)}
        # also surface a few other files if present
        for extra in ["user-settings.json", "settings.json"]:
            p = grok_home / extra
            if p.exists():
                try:
                    out[extra] = json.loads(p.read_text())
                except Exception:
                    pass
        console.print(json.dumps(out, indent=2))
        return

    if not cfg:
        warn("No config.toml or empty.")
        info(f"Location: {grok_home / 'config.toml'}")
        return

    t = make_table("Config (config.toml)", ["Section", "Key", "Value"])
    for section, vals in sorted(cfg.items()):
        if isinstance(vals, dict):
            for k, v in sorted(vals.items()):
                t.add_row(section, k, str(v)[:60])
        else:
            t.add_row(section, "", str(vals)[:60])
    console.print(t)

    # show a couple of other well-known files
    for name in ["user-settings.json", "settings.json"]:
        p = grok_home / name
        if p.exists():
            try:
                data = json.loads(p.read_text())
                console.print(f"\n[bold]{name}[/bold]")
                console.print(data)
            except Exception:
                pass


@app.command("get")
def get_key(
    ctx: typer.Context,
    key: str = typer.Argument(
        ..., help="Dotted key e.g. ui.permission_mode or mcp_servers.myfs.command"
    ),
    json_out: bool = typer.Option(False, "--json"),
) -> None:
    """Get a single value from the loaded config."""
    grok_home = get_grok_home(ctx.obj.get("grok_home") if ctx.obj else None)
    cfg = load_config(grok_home)

    # naive dotted lookup
    parts = key.split(".")
    val: object = cfg
    for p in parts:
        if isinstance(val, dict) and p in val:
            val = val[p]
        else:
            val = None
            break

    if json_out:
        import json

        console.print(json.dumps({"key": key, "value": val}, indent=2))
        return

    if val is None:
        warn(f"Key '{key}' not found (or not in top sections).")
    else:
        console.print(f"{key} = {val}")


@app.command("paths")
def show_paths(ctx: typer.Context) -> None:
    """Show important Grok directories and files (very handy for scripting)."""
    grok_home = get_grok_home(ctx.obj.get("grok_home") if ctx.obj else None)

    rows = [
        ("grok_home", str(grok_home)),
        ("config", str(grok_home / "config.toml")),
        ("sessions", str(grok_home / "sessions")),
        ("skills (user)", str(grok_home / "skills")),
        ("plugins (user)", str(grok_home / "plugins")),
        ("hooks (user)", str(grok_home / "hooks")),
        ("logs", str(grok_home / "logs" / "unified.jsonl")),
        ("bin/grok", str(grok_home / "bin" / "grok")),
    ]
    t = make_table("Grok Paths", ["Name", "Path"])
    for name, p in rows:
        t.add_row(name, p)
    console.print(t)


@app.command("validate")
def validate_config(ctx: typer.Context, json_out: bool = typer.Option(False, "--json")) -> None:
    """Light structural validation / sanity checks on config."""
    grok_home = get_grok_home(ctx.obj.get("grok_home") if ctx.obj else None)
    cfg = load_config(grok_home)

    issues: list[str] = []
    if not cfg:
        issues.append("config.toml missing or unparsable")

    # example checks
    ui = cfg.get("ui", {}) if isinstance(cfg.get("ui"), dict) else {}
    if ui.get("permission_mode") not in (
        None,
        "always-approve",
        "default",
        "plan",
        "bypassPermissions",
    ):
        issues.append(f"unusual permission_mode: {ui.get('permission_mode')}")

    if json_out:
        import json

        console.print(
            json.dumps(
                {"ok": len(issues) == 0, "issues": issues, "sections": list(cfg.keys())}, indent=2
            )
        )
        return

    if issues:
        for i in issues:
            warn(i)
    else:
        success("Basic config looks sane.")
    info(f"Full file: {grok_home / 'config.toml'}")
