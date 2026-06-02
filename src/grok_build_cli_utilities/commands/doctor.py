"""grok-utils doctor - environment and setup health check."""

from __future__ import annotations

import platform
import sys
from pathlib import Path
from typing import Any

import typer

from .. import __version__
from ..utils.common import (
    console,
    get_grok_home,
    get_sessions_dir,
    info,
    iter_sessions,
    make_table,
    success,
    warn,
)
from ..utils.parsers import iter_skills
from .mcp import _load_config  # reuse the config loader (best effort)


def _check_exists(p: Path, label: str) -> tuple[str, str]:
    if p.exists():
        return "✓", f"{label} present"
    return "✗", f"{label} missing"


def _safe_count_sessions(grok_home: Path) -> int:
    try:
        return len(list(iter_sessions(grok_home)))
    except Exception:
        return -1


def _safe_count_skills(grok_home: Path) -> int:
    try:
        return len(iter_skills(grok_home))
    except Exception:
        return -1


def _safe_mcp_count(grok_home: Path) -> int:
    try:
        cfg = _load_config(grok_home)
        m = cfg.get("mcp_servers", {}) if isinstance(cfg.get("mcp_servers"), dict) else {}
        return len(m)
    except Exception:
        return -1


def doctor(
    ctx: typer.Context,
    json_out: bool = typer.Option(False, "--json", help="Output structured JSON for scripting/CI"),
) -> None:
    """Run health checks on your Grok Build installation and grok-utils setup."""
    grok_home = get_grok_home(ctx.obj.get("grok_home") if ctx.obj else None)

    checks: list[dict[str, Any]] = []

    # Basic env
    checks.append(
        {
            "name": "Python",
            "status": "✓",
            "detail": f"{sys.version.split()[0]} on {platform.system()} {platform.release()}",
        }
    )
    checks.append({"name": "grok-utils", "status": "✓", "detail": f"v{__version__} (importable)"})

    # Grok home
    status, detail = _check_exists(grok_home, "Grok home")
    checks.append({"name": "Grok home", "status": status, "detail": f"{grok_home} ({detail})"})

    if grok_home.exists():
        try:
            # Writable test (touch a temp file)
            testf = grok_home / ".grok-utils-doctor-test"
            testf.write_text("ok", encoding="utf-8")
            testf.unlink(missing_ok=True)
            checks.append({"name": "Grok home writable", "status": "✓", "detail": "yes"})
        except Exception as e:
            checks.append({"name": "Grok home writable", "status": "✗", "detail": str(e)[:60]})

    # Core dirs
    sess_dir = get_sessions_dir(grok_home)
    s = "✓" if sess_dir.exists() else "⚠"
    checks.append({"name": "Sessions dir", "status": s, "detail": str(sess_dir)})

    n_sessions = _safe_count_sessions(grok_home)
    checks.append(
        {
            "name": "Sessions found",
            "status": "✓" if n_sessions >= 0 else "⚠",
            "detail": str(n_sessions) if n_sessions >= 0 else "scan error",
        }
    )

    # Skills (from all scopes)
    n_skills = _safe_count_skills(grok_home)
    checks.append(
        {
            "name": "Skills discovered",
            "status": "✓" if n_skills > 0 else ("⚠" if n_skills == 0 else "✗"),
            "detail": str(n_skills),
        }
    )

    # MCP
    n_mcp = _safe_mcp_count(grok_home)
    checks.append(
        {
            "name": "MCP servers (config)",
            "status": "✓" if n_mcp > 0 else "⚠",
            "detail": str(n_mcp),
        }
    )

    # Grok binary (the one mcp etc try to delegate to)
    grok_bin = grok_home / "bin" / "grok"
    s, d = _check_exists(grok_bin, "grok bin")
    checks.append({"name": "Grok CLI binary", "status": s, "detail": str(grok_bin)})

    # Backups convention
    backups = Path.home() / "grok-backups"
    s, d = _check_exists(backups, "Backups dir")
    checks.append(
        {
            "name": "Backups convention",
            "status": "⚠" if not backups.exists() else "✓",
            "detail": str(backups),
        }
    )

    # Memory (experimental)
    mem = grok_home / "memory"
    s = "✓" if mem.exists() else "⚠"
    checks.append({"name": "Memory dir (experimental)", "status": s, "detail": str(mem)})

    if json_out:
        import json

        console.print(json.dumps({"grok_home": str(grok_home), "checks": checks}, indent=2))
        return

    # Pretty output
    t = make_table("grok-utils doctor", ["Check", "Status", "Detail"])
    for c in checks:
        t.add_row(c["name"], c["status"], c["detail"][:70])

    console.print(t)

    # Summary advice
    missing = [c for c in checks if c["status"] in ("✗", "⚠")]
    if not missing:
        success("All checks look good. You're ready to use the power tools!")
    else:
        warn(f"{len(missing)} items with warnings or errors above.")
        info("Use --grok-home to point at a different installation.")
        info("Many commands are safe-by-default (dry-run) even if setup is partial.")

    # Quick tips
    console.print(
        "\n[dim]Tips: grok-utils sessions list | usage report | skills list | backup create --help[/dim]"
    )
