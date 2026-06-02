"""grok-utils mcp - enhanced MCP server tooling."""

from __future__ import annotations

import subprocess
from pathlib import Path

try:
    import tomli
except ImportError:
    tomli = None  # type: ignore[assignment]

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

app = typer.Typer(help="MCP server power tools and diagnostics", no_args_is_help=True)


def _load_config(grok_home: Path) -> dict:
    cfg = grok_home / "config.toml"
    if not cfg.exists():
        return {}
    try:
        with open(cfg, "rb") as f:
            if tomli is not None:
                return tomli.load(f)  # type: ignore[no-any-return]
            else:
                # very naive toml reader for name = "value" under [mcp_servers.xxx]
                # sufficient for the doctor/list use case
                data: dict[str, dict] = {}
                current: str | None = None
                text = f.read().decode("utf-8", errors="ignore")
                for raw in text.splitlines():
                    line = raw.strip()
                    if line.startswith("[mcp_servers."):
                        current = line[1:-1].split(".", 1)[1]
                        data.setdefault(current, {})
                    elif "=" in line and current:
                        k, v = [x.strip().strip("\"'") for x in line.split("=", 1)]
                        data[current][k] = v
                return {"mcp_servers": data}
    except Exception:
        return {}


@app.command("list")
def list_mcp(ctx: typer.Context) -> None:
    """List configured MCP servers from config + what grok sees."""
    grok_home = get_grok_home(ctx.obj.get("grok_home") if ctx.obj else None)
    cfg = _load_config(grok_home)

    mcp_section = cfg.get("mcp_servers", {}) if isinstance(cfg.get("mcp_servers"), dict) else {}

    t = make_table("MCP Servers (config.toml)", ["Name", "Command / URL", "Env/Notes"])
    for name, spec in mcp_section.items():
        if isinstance(spec, dict):
            cmd = spec.get("command") or spec.get("url") or str(spec)[:60]
            env = ", ".join(spec.get("env", {}).keys()) if spec.get("env") else ""
            t.add_row(name, str(cmd)[:55], env)
        else:
            t.add_row(name, str(spec)[:55], "")
    if mcp_section:
        console.print(t)
    else:
        info("No [mcp_servers] section in config.toml (or empty)")

    # also try grok mcp list if the local grok binary is present (best effort)
    grok_bin = grok_home / "bin" / "grok"
    if grok_bin.exists():
        try:
            out = subprocess.run(
                [str(grok_bin), "mcp", "list"],
                capture_output=True,
                text=True,
                timeout=8,
            )
            if out.returncode == 0 and out.stdout.strip():
                console.print("\n[bold]grok mcp list output:[/bold]")
                console.print(out.stdout.strip())
        except Exception:
            pass


@app.command("doctor")
def doctor(ctx: typer.Context) -> None:
    """Health check MCP servers (config presence + basic reachability hints)."""
    grok_home = get_grok_home(ctx.obj.get("grok_home") if ctx.obj else None)
    cfg = _load_config(grok_home)
    mcp_section: dict = (
        cfg.get("mcp_servers", {}) if isinstance(cfg.get("mcp_servers"), dict) else {}
    )

    if not mcp_section:
        warn("No MCP servers configured.")
        info("Add with: grok mcp add ... or edit ~/.grok/config.toml")
        return

    console.print("[bold]Running basic MCP doctor...[/bold]\n")

    for name, spec in mcp_section.items():
        console.print(f"[cyan]{name}[/cyan]")
        if isinstance(spec, dict):
            cmd = spec.get("command")
            if cmd:
                # very light check: does the binary exist on PATH?
                import shutil

                exe = cmd.split()[0]
                if shutil.which(exe):
                    success(f"  command '{exe}' found on PATH")
                else:
                    warn(f"  command '{exe}' NOT found on PATH")
            args = spec.get("args", [])
            if args:
                info(f"  args: {' '.join(args)}")
        else:
            info(f"  spec: {spec}")
        console.print()


@app.command("test")
def test_server(
    ctx: typer.Context,
    name: str = typer.Argument(..., help="MCP server name from config"),
) -> None:
    """Attempt a very lightweight test (uses `grok mcp` if possible)."""
    grok_home = get_grok_home(ctx.obj.get("grok_home") if ctx.obj else None)

    try:
        out = subprocess.run(
            [str(grok_home / "bin" / "grok"), "mcp", "details", name],
            capture_output=True,
            text=True,
            timeout=12,
        )
        if out.returncode == 0:
            success(f"grok mcp details for {name}:")
            console.print(out.stdout)
        else:
            warn(f"grok mcp returned {out.returncode}")
            console.print(out.stderr[:800] or out.stdout[:800])
    except Exception as e:
        error(f"Could not invoke grok mcp: {e}")
        info("You can still run `grok mcp list` / `grok mcp details <name>` manually.")


@app.command("add-example")
def add_example(
    ctx: typer.Context,
    name: str = typer.Argument(..., help="Short name for the server"),
    kind: str = typer.Option(
        "filesystem", "--kind", help="Example kind: filesystem | github | sqlite"
    ),
) -> None:
    """Append a well-known example MCP server config (you must edit paths/tokens)."""
    grok_home = get_grok_home(ctx.obj.get("grok_home") if ctx.obj else None)
    cfg_path = grok_home / "config.toml"

    examples = {
        "filesystem": f"""
[mcp_servers.{name}]
command = "npx"
args = ["-y", "@modelcontextprotocol/server-filesystem", "/path/to/allowed/dir"]
""",
        "github": f"""
[mcp_servers.{name}]
command = "npx"
args = ["-y", "@modelcontextprotocol/server-github"]
env = {{ GITHUB_PERSONAL_ACCESS_TOKEN = "ghp_xxx" }}
""",
        "sqlite": f"""
[mcp_servers.{name}]
command = "uvx"
args = ["mcp-server-sqlite", "--db-path", "/tmp/example.db"]
""",
    }

    if kind not in examples:
        error(f"Unknown kind {kind}. Try: {', '.join(examples)}")
        raise typer.Exit(1)

    snippet = examples[kind]
    with open(cfg_path, "a", encoding="utf-8") as f:
        f.write("\n" + snippet + "\n")

    success(f"Appended example '{kind}' as mcp_servers.{name} to {cfg_path}")
    warn("Edit the file to set real paths and secrets, then restart Grok.")
