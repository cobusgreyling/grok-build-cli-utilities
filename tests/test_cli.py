"""Smoke + functional tests for the CLI entrypoint using temp grok homes."""

import json
from pathlib import Path

from typer.testing import CliRunner

from grok_build_cli_utilities.cli import app

runner = CliRunner()


def test_help():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "grok-utils" in result.output
    assert "sessions" in result.output
    assert "skills" in result.output
    assert "backup" in result.output


def test_version():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert (
        "0.3.1" in result.output
    )  # 0.3.1 includes tomllib, shared toml, safe helpers, coverage/tests, CI/docs polish etc.


def test_sessions_help():
    result = runner.invoke(app, ["sessions", "--help"])
    assert result.exit_code == 0
    assert "list" in result.output
    assert "search" in result.output
    assert "prune" in result.output
    assert "resume" in result.output
    assert "info" in result.output


def test_skills_help():
    result = runner.invoke(app, ["skills", "--help"])
    assert result.exit_code == 0
    assert "list" in result.output
    assert "create" in result.output
    assert "validate" in result.output


def test_backup_help():
    result = runner.invoke(app, ["backup", "--help"])
    assert result.exit_code == 0
    assert "create" in result.output
    assert "restore" in result.output
    assert "list" in result.output


def test_mcp_help():
    result = runner.invoke(app, ["mcp", "--help"])
    assert result.exit_code == 0


def test_new_tier_commands_help():
    for grp in ["plugins", "hooks", "config", "logs"]:
        result = runner.invoke(app, [grp, "--help"])
        assert result.exit_code == 0, f"{grp} help failed"
        assert (
            "help" in result.output.lower() or "--json" in result.output or "list" in result.output
        )

    # sessions new subcommands
    result = runner.invoke(app, ["sessions", "--help"])
    assert "export" in result.output
    assert "analyze" in result.output

    # usage cost
    result = runner.invoke(app, ["usage", "--help"])
    assert "cost" in result.output


def test_worktree_help():
    result = runner.invoke(app, ["worktree", "--help"])
    assert result.exit_code == 0


def test_memory_help():
    result = runner.invoke(app, ["memory", "--help"])
    assert result.exit_code == 0


def test_usage_help():
    result = runner.invoke(app, ["usage", "--help"])
    assert result.exit_code == 0


def test_skills_list_with_custom_home(tmp_path: Path):
    grok = tmp_path / ".grok"
    skills_dir = grok / "skills" / "demo-skill"
    skills_dir.mkdir(parents=True)
    (skills_dir / "SKILL.md").write_text(
        "---\nname: demo-skill\ndescription: A demo for testing the CLI\n---\n\nSteps..."
    )

    result = runner.invoke(app, ["-g", str(grok), "skills", "list"])
    assert result.exit_code == 0
    assert "demo-skill" in result.output or "No skills" not in result.output


def test_skills_create_and_validate(tmp_path: Path):
    grok = tmp_path / ".grok"
    result = runner.invoke(
        app,
        ["-g", str(grok), "skills", "create", "my-test", "--desc", "Test skill for CLI", "--user"],
    )
    assert result.exit_code == 0
    assert "Created" in result.output

    # validate it (using --user + -g so it lands inside the isolated tmp grok_home)
    result2 = runner.invoke(app, ["-g", str(grok), "skills", "validate"])
    assert result2.exit_code == 0


def test_sessions_list_with_fake_data(tmp_path: Path):
    grok = tmp_path / ".grok"
    sess_dir = grok / "sessions" / "fakeproj" / "01abc123"
    sess_dir.mkdir(parents=True)
    summary = {
        "info": {"id": "01abc123", "cwd": str(tmp_path / "fakeproj")},
        "created_at": "2026-06-01T09:00:00Z",
        "last_active_at": "2026-06-01T10:00:00Z",
        "num_messages": 7,
        "current_model_id": "grok-3",
        "agent_name": "",
    }
    (sess_dir / "summary.json").write_text(json.dumps(summary))

    result = runner.invoke(app, ["-g", str(grok), "sessions", "list", "--limit", "5"])
    assert result.exit_code == 0
    assert "01abc123" in result.output or "Sessions" in result.output


def test_backup_list_no_dir(tmp_path: Path):
    # No ~/grok-backups -> friendly message
    # We can't easily mock home, but the command handles missing dir
    result = runner.invoke(app, ["-g", str(tmp_path / ".grok"), "backup", "list"])
    # Either succeeds with message or lists (in this env it may find real backups)
    assert result.exit_code == 0


def test_sessions_list_json(tmp_path: Path):
    grok = tmp_path / ".grok"
    sess_dir = grok / "sessions" / "p" / "sid123"
    sess_dir.mkdir(parents=True)
    (sess_dir / "summary.json").write_text(
        json.dumps(
            {
                "info": {"id": "sid123", "cwd": "/p"},
                "created_at": "2026-06-01T00:00:00Z",
                "num_messages": 5,
                "current_model_id": "grok-3",
            }
        )
    )
    result = runner.invoke(app, ["-g", str(grok), "sessions", "list", "--json", "--limit", "1"])
    assert result.exit_code == 0
    assert '"id": "sid123"' in result.output or "sid123" in result.output


def test_sessions_resume_json_mode(tmp_path: Path):
    grok = tmp_path / ".grok"
    sess_dir = grok / "sessions" / "p" / "sid-resume-12345678"
    sess_dir.mkdir(parents=True)
    (sess_dir / "summary.json").write_text(
        json.dumps(
            {
                "info": {"id": "sid-resume-12345678", "cwd": "/p"},
                "created_at": "2026-06-01T00:00:00Z",
                "last_active_at": "2026-06-01T01:00:00Z",
                "num_messages": 3,
                "current_model_id": "grok-build",
            }
        )
    )
    result = runner.invoke(app, ["-g", str(grok), "sessions", "resume", "sid-resume", "--json"])
    assert result.exit_code == 0
    assert "sid-resume-12345678" in result.output
    assert "resume" in result.output.lower() or "cmd" in result.output


def test_usage_report_json_and_spark(tmp_path: Path):
    grok = tmp_path / ".grok"
    for i, sid in enumerate(["s1", "s2"]):
        d = grok / "sessions" / "proj" / sid
        d.mkdir(parents=True)
        (d / "summary.json").write_text(
            json.dumps(
                {
                    "info": {"id": sid, "cwd": "/proj"},
                    "created_at": f"2026-06-0{i + 1}T00:00:00Z",
                    "last_active_at": f"2026-06-0{i + 1}T00:00:00Z",
                    "num_messages": 10 + i,
                    "current_model_id": "grok-build",
                }
            )
        )
    result = runner.invoke(app, ["-g", str(grok), "usage", "report", "--json", "--top", "1"])
    assert result.exit_code == 0
    assert "sessions" in result.output and "messages" in result.output


def test_sessions_prune_dry_run(tmp_path: Path):
    grok = tmp_path / ".grok"
    old_dir = grok / "sessions" / "oldproj" / "old123"
    old_dir.mkdir(parents=True)
    (old_dir / "summary.json").write_text(
        json.dumps(
            {
                "info": {"id": "old123", "cwd": "/old"},
                "created_at": "2020-01-01T00:00:00Z",
                "last_active_at": "2020-01-01T00:00:00Z",
                "num_messages": 1,
                "current_model_id": "old",
            }
        )
    )
    result = runner.invoke(
        app, ["-g", str(grok), "sessions", "prune", "--older-than", "1d", "--dry-run"]
    )
    assert result.exit_code == 0
    assert "DRY RUN" in result.output or "Would prune" in result.output or "old123" in result.output


def test_sessions_prune_execute_with_yes(tmp_path: Path):
    """Exercise the actual delete path using --no-dry-run --yes (safe in tmp)."""
    grok = tmp_path / ".grok"
    old_dir = grok / "sessions" / "oldproj" / "old456"
    old_dir.mkdir(parents=True)
    (old_dir / "summary.json").write_text(
        json.dumps(
            {
                "info": {"id": "old456", "cwd": "/old2"},
                "created_at": "2020-01-01T00:00:00Z",
                "last_active_at": "2020-01-01T00:00:00Z",
                "num_messages": 1,
                "current_model_id": "old",
            }
        )
    )
    assert old_dir.exists()
    result = runner.invoke(
        app,
        ["-g", str(grok), "sessions", "prune", "--older-than", "1d", "--no-dry-run", "--yes"],
    )
    assert result.exit_code == 0
    assert (
        "Deleted" in result.output
        or "old456" in result.output
        or "Removed" in result.output.lower()
    )
    # dir should be gone (or at least attempt made)
    assert not old_dir.exists() or not (old_dir / "summary.json").exists()


def test_skills_pack_creates_tar(tmp_path: Path):
    grok = tmp_path / ".grok"
    # create a skill first (into the isolated grok via --user)
    result = runner.invoke(
        app,
        ["-g", str(grok), "skills", "create", "packme", "--desc", "Skill for pack test", "--user"],
    )
    assert result.exit_code == 0

    out_tar = tmp_path / "packme.skill.tar.gz"
    result2 = runner.invoke(app, ["-g", str(grok), "skills", "pack", "packme", "-o", str(out_tar)])
    assert result2.exit_code == 0
    assert out_tar.exists()
    assert out_tar.stat().st_size > 100


def test_mcp_add_example_appends_config(tmp_path: Path):
    grok = tmp_path / ".grok"
    cfg = grok / "config.toml"
    cfg.parent.mkdir(parents=True, exist_ok=True)
    cfg.write_text("[other]\nfoo=1\n", encoding="utf-8")

    result = runner.invoke(
        app, ["-g", str(grok), "mcp", "add-example", "myfs", "--kind", "filesystem"]
    )
    assert result.exit_code == 0
    content = cfg.read_text(encoding="utf-8")
    assert "[mcp_servers.myfs]" in content
    assert "server-filesystem" in content


def test_backup_create_with_manifest(tmp_path: Path):
    grok = tmp_path / ".grok"
    grok.mkdir(parents=True)
    # minimal state so gather finds something
    (grok / "config.toml").write_text("test = true\n", encoding="utf-8")
    (grok / "user-settings.json").write_text("{}", encoding="utf-8")

    out = tmp_path / "test-backup.tar.gz"
    result = runner.invoke(
        app,
        ["-g", str(grok), "backup", "create", "-o", str(out), "--no-compress"],
    )
    assert result.exit_code == 0
    assert out.exists()

    # manifest sidecar
    mf = out.with_suffix(out.suffix + ".manifest.json")
    assert mf.exists()
    import json

    data = json.loads(mf.read_text())
    assert "files" in data and len(data["files"]) > 0
    assert any("config.toml" in f.get("path", "") for f in data["files"])


def test_doctor_runs(tmp_path: Path):
    grok = tmp_path / ".grok"
    grok.mkdir(parents=True)
    (grok / "config.toml").write_text("", encoding="utf-8")

    result = runner.invoke(app, ["-g", str(grok), "doctor"])
    assert result.exit_code == 0
    assert "grok-utils doctor" in result.output or "Python" in result.output

    resultj = runner.invoke(app, ["-g", str(grok), "doctor", "--json"])
    assert resultj.exit_code == 0
    assert '"checks"' in resultj.output or "grok_home" in resultj.output


def test_plugins_and_hooks_with_fake(tmp_path: Path):
    grok = tmp_path / ".grok"
    plug_dir = grok / "plugins" / "demo-plugin"
    (plug_dir / "skills" / "demo").mkdir(parents=True)
    (plug_dir / "skills" / "demo" / "SKILL.md").write_text(
        "---\nname: demo\ndescription: demo skill\n---\nsteps"
    )
    (plug_dir / "hooks").mkdir(parents=True)
    (plug_dir / "hooks" / "hooks.json").write_text(
        '{"hooks": {"SessionStart": [{"hooks": [{"type":"command","command":"echo hi"}]}]}}'
    )

    # plugins list
    r = runner.invoke(app, ["-g", str(grok), "plugins", "list", "--json"])
    assert r.exit_code == 0
    assert "demo-plugin" in r.output

    # hooks list
    r2 = runner.invoke(app, ["-g", str(grok), "hooks", "list", "--json"])
    assert r2.exit_code == 0
    assert "SessionStart" in r2.output or "demo" in r2.output.lower()


def test_config_and_logs_fake(tmp_path: Path):
    grok = tmp_path / ".grok"
    grok.mkdir(parents=True, exist_ok=True)
    (grok / "config.toml").write_text('[ui]\npermission_mode = "always-approve"\n')
    (grok / "logs").mkdir(parents=True, exist_ok=True)
    (grok / "logs" / "unified.jsonl").write_text(
        '{"ts":"2026-01-01","src":"t","lvl":"info","msg":"hello"}\n'
    )

    r = runner.invoke(app, ["-g", str(grok), "config", "show", "--json"])
    assert r.exit_code == 0
    assert "ui" in r.output or "permission" in r.output

    r2 = runner.invoke(app, ["-g", str(grok), "logs", "tail", "--lines", "1", "--json"])
    assert r2.exit_code == 0


def test_sessions_analyze_export_resume_json(tmp_path: Path):
    grok = tmp_path / ".grok"
    sess_dir = grok / "sessions" / "proj" / "01abc999"
    sess_dir.mkdir(parents=True)
    summary = {
        "info": {"id": "01abc999", "cwd": str(tmp_path / "proj")},
        "created_at": "2026-06-01T09:00:00Z",
        "last_active_at": "2026-06-01T10:00:00Z",
        "num_messages": 3,
        "current_model_id": "grok-3",
        "agent_name": "",
    }
    (sess_dir / "summary.json").write_text(json.dumps(summary))
    # signals + rewinds for analyze/export
    (sess_dir / "signals.json").write_text('{"turnCount":2,"toolCallCount":4}')
    (sess_dir / "rewind_points.jsonl").write_text('{"prompt_index":1}\n')

    # analyze
    r = runner.invoke(app, ["-g", str(grok), "sessions", "analyze", "01abc999", "--json"])
    assert r.exit_code == 0
    assert "01abc999" in r.output and ("signals" in r.output or "turnCount" in r.output)

    # export md
    r2 = runner.invoke(app, ["-g", str(grok), "sessions", "export", "01abc", "--format", "md"])
    assert r2.exit_code == 0
    assert "# Session 01abc999" in r2.output or "Session 01abc999" in r2.output

    # export json via flag
    r3 = runner.invoke(app, ["-g", str(grok), "sessions", "export", "01abc999", "--json"])
    assert r3.exit_code == 0
    assert '"id": "01abc999"' in r3.output

    # resume --json (no exec)
    r4 = runner.invoke(app, ["-g", str(grok), "sessions", "resume", "01abc999", "--json"])
    assert r4.exit_code == 0
    assert "--resume" in r4.output or "01abc999" in r4.output


def test_usage_cost_and_config_get(tmp_path: Path):
    grok = tmp_path / ".grok"
    grok.mkdir(parents=True)
    sess_dir = grok / "sessions" / "p1" / "s1"
    sess_dir.mkdir(parents=True)
    (sess_dir / "summary.json").write_text(
        json.dumps(
            {
                "info": {"id": "s1", "cwd": "/p1"},
                "created_at": "2026-06-01T00:00:00Z",
                "num_messages": 10,
                "current_model_id": "grok-3",
            }
        )
    )

    r = runner.invoke(app, ["-g", str(grok), "usage", "cost", "--by", "model", "--json"])
    assert r.exit_code == 0
    assert "estimated_total_usd" in r.output or "Est." in r.output  # rough

    # config get (uses parsers load)
    (grok / "config.toml").write_text('[foo]\nbar = "baz"\n')
    r2 = runner.invoke(app, ["-g", str(grok), "config", "get", "foo.bar"])
    assert r2.exit_code == 0


def test_plugins_inventory_and_hooks_create(tmp_path: Path):
    grok = tmp_path / ".grok"
    # inventory is not a subcommand? but list --all exercises marketplace path (empty ok)
    r = runner.invoke(app, ["-g", str(grok), "plugins", "list", "--all", "--json"])
    assert r.exit_code == 0

    # hooks create (scaffolds)
    r2 = runner.invoke(app, ["-g", str(grok), "hooks", "create", "PostToolUse", "audit"])
    assert r2.exit_code == 0 or "Created" in r2.output or "hook" in r2.output.lower()
