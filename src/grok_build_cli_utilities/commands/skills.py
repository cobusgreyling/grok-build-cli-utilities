"""grok-utils skills - discovery, validation, scaffolding."""

from __future__ import annotations

import tarfile
from pathlib import Path
from typing import Optional

import typer

from ..utils.common import (
    console,
    error,
    get_grok_home,
    make_table,
    Panel,
    success,
    warn,
)
from ..utils.parsers import (
    Skill,
    iter_skills,
    parse_skill,
    skill_template,
    validate_skill,
)

app = typer.Typer(help="Manage Grok Build skills across all locations", no_args_is_help=True)


@app.command("list")
def list_skills(
    ctx: typer.Context,
    all: bool = typer.Option(False, "--all", "-a", help="Show even lower priority / compat skills"),
    json_out: bool = typer.Option(False, "--json"),
) -> None:
    """List all discovered skills (deduped by priority)."""
    grok_home = get_grok_home(ctx.obj.get("grok_home") if ctx.obj else None)
    skills = iter_skills(grok_home)

    if not all:
        # already deduped in iter
        pass

    if json_out:
        import json

        console.print(
            json.dumps(
                [
                    {
                        "name": s.name,
                        "scope": s.scope,
                        "path": str(s.path),
                        "desc": s.description[:80],
                    }
                    for s in skills
                ],
                indent=2,
            )
        )
        return

    if not skills:
        warn("No skills discovered. Create one with [bold]grok-utils skills create[/bold]")
        return

    t = make_table(f"Discovered Skills ({len(skills)})", ["Name", "Scope", "Description", "Path"])
    for s in skills:
        t.add_row(
            f"[bold cyan]{s.name}[/bold cyan]",
            s.scope,
            s.description[:65] + ("…" if len(s.description) > 65 else ""),
            str(s.path.relative_to(Path.home()))
            if str(s.path).startswith(str(Path.home()))
            else str(s.path),
        )
    console.print(t)
    console.print(
        "\n[dim]Scopes: local > repo > user > claude/cursor (compat). Higher wins on name collision.[/dim]"
    )


@app.command("info")
def info(
    ctx: typer.Context,
    name: str = typer.Argument(..., help="Skill name"),
) -> None:
    """Show full details + validation for a skill."""
    grok_home = get_grok_home(ctx.obj.get("grok_home") if ctx.obj else None)
    for s in iter_skills(grok_home):
        if s.name == name.lower():
            errs = validate_skill(s)
            status = "[green]valid[/green]" if not errs else "[red]INVALID[/red]"
            console.print(
                Panel.fit(
                    f"Name: [bold]{s.name}[/bold]\n"
                    f"Scope: {s.scope}\n"
                    f"Path: {s.path}\n"
                    f"Status: {status}\n\n"
                    f"Description:\n{s.description}\n\n"
                    f"Frontmatter keys: {', '.join(s.frontmatter.keys()) or '(none)'}\n"
                    f"Body length: {len(s.content)} chars",
                    title=f"Skill: {s.name}",
                    border_style="cyan" if not errs else "red",
                )
            )
            if errs:
                for e in errs:
                    error(f"  • {e}")
            return
    error(f"Skill '{name}' not found")


@app.command("create")
def create(
    ctx: typer.Context,
    name: str = typer.Argument(..., help="Skill name (slug)"),
    description: str = typer.Option(
        ..., "--desc", "-d", prompt=True, help="One-line description for invocation"
    ),
    local: bool = typer.Option(
        True, "--local/--user", help="Create in ./.grok/skills (default) or ~/.grok/skills"
    ),
    force: bool = typer.Option(False, "--force", help="Overwrite if exists"),
) -> None:
    """Scaffold a new high-quality SKILL.md."""
    grok_home = get_grok_home(ctx.obj.get("grok_home") if ctx.obj else None)

    if local:
        target_dir = Path.cwd() / ".grok" / "skills" / name
    else:
        target_dir = grok_home / "skills" / name

    target_dir.mkdir(parents=True, exist_ok=True)
    md_path = target_dir / "SKILL.md"

    if md_path.exists() and not force:
        error(f"{md_path} already exists. Use --force to overwrite.")
        raise typer.Exit(1)

    content = skill_template(name, description)
    md_path.write_text(content, encoding="utf-8")
    success(f"Created {md_path}")
    console.print(
        "Edit it, then test with [cyan]grok[/cyan] or validate via [bold]grok-utils skills validate[/bold]"
    )


@app.command("validate")
def validate(
    ctx: typer.Context,
    path: Optional[Path] = typer.Argument(
        None, help="Path to skill dir or SKILL.md (defaults to scan all)"
    ),
) -> None:
    """Validate one or all skills. Exits non-zero on any error."""
    grok_home = get_grok_home(ctx.obj.get("grok_home") if ctx.obj else None)
    bad = 0

    if path:
        p = Path(path).resolve()
        if p.is_file():
            p = p.parent
        s = parse_skill(p)
        if not s:
            error("No SKILL.md found or unparsable")
            raise typer.Exit(1)
        errs = validate_skill(s)
        if errs:
            bad += 1
            for e in errs:
                error(f"{s.name}: {e}")
        else:
            success(f"{s.name} looks good")
    else:
        for s in iter_skills(grok_home):
            errs = validate_skill(s)
            if errs:
                bad += 1
                console.print(f"[red]✗[/red] {s.name} ({s.scope})")
                for e in errs:
                    console.print(f"    [dim]{e}[/dim]")
            else:
                console.print(f"[green]✓[/green] {s.name}")

    if bad:
        error(f"{bad} skill(s) have issues")
        raise typer.Exit(2)
    success("All good!")


@app.command("pack")
def pack(
    ctx: typer.Context,
    name: str = typer.Argument(..., help="Skill name to pack"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output .tar.gz path"),
) -> None:
    """Package a skill directory into a portable .tar.gz (for sharing or backup)."""
    grok_home = get_grok_home(ctx.obj.get("grok_home") if ctx.obj else None)
    skill: Optional[Skill] = None
    for s in iter_skills(grok_home):
        if s.name == name.lower():
            skill = s
            break
    if not skill:
        error(f"Skill {name} not found")
        raise typer.Exit(1)

    out = output or Path.cwd() / f"{skill.name}.skill.tar.gz"
    with tarfile.open(out, "w:gz") as tar:
        tar.add(skill.path, arcname=skill.name)
    success(f"Packed to {out}")
    console.print("Recipients can unpack with [bold]grok-utils skills unpack <file>[/bold]")


@app.command("unpack")
def unpack(
    ctx: typer.Context,
    archive: Path = typer.Argument(..., exists=True, help="The .tar.gz created by pack"),
    dest: Optional[Path] = typer.Option(
        None, "--dest", "-d", help="Where to extract (default: ~/.grok/skills)"
    ),
) -> None:
    """Unpack a .skill.tar.gz into your user skills dir (or --dest)."""
    grok_home = get_grok_home(ctx.obj.get("grok_home") if ctx.obj else None)
    target = dest or (grok_home / "skills")
    target.mkdir(parents=True, exist_ok=True)

    with tarfile.open(archive, "r:gz") as tar:
        # safe extract: first member should be the skill dir
        members = tar.getmembers()
        if not members:
            error("Empty archive")
            raise typer.Exit(1)
        root = members[0].name.split("/")[0]
        tar.extractall(target)
    success(f"Unpacked {root} into {target}")
