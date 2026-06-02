"""Basic and expanded tests for shared utilities (including new safety helpers)."""

import json
import tarfile
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

from grok_build_cli_utilities.utils.common import (
    get_grok_home,
    get_sessions_dir,
    get_skills_dirs,
    parse_timestamp,
    format_age,
    format_dt,
    iter_sessions,
    load_session_updates,
    count_tool_calls,
    make_table,
    safe_extract_tar,
    SessionSummary,
)
from grok_build_cli_utilities.utils.parsers import (
    parse_skill,
    skill_template,
    validate_skill,
    Skill,
)


def test_get_grok_home_default():
    h = get_grok_home()
    assert h.name == ".grok"
    assert h.is_absolute()


def test_get_grok_home_custom():
    p = Path("/tmp/fake-grok")
    assert get_grok_home(p) == p.resolve()


def test_get_sessions_dir():
    h = get_grok_home(Path("/tmp/testg"))
    sessions_dir = get_sessions_dir(h)
    # Use .resolve() comparison or name checks because on macOS /tmp symlinks to /private/tmp
    assert sessions_dir == (h / "sessions").resolve() or sessions_dir.name == "sessions"


def test_get_skills_dirs_structure():
    h = get_grok_home(Path("/tmp/testg"))
    dirs = get_skills_dirs(h)
    scopes = [d[0] for d in dirs]
    assert "local" in scopes and "user" in scopes and "repo" in scopes


def test_parse_timestamp():
    assert parse_timestamp("2026-05-27T14:46:06.413248Z") is not None
    assert parse_timestamp(1716821166) is not None
    assert parse_timestamp(1716821166000) is not None  # millis
    assert parse_timestamp(None) is None
    assert parse_timestamp("bad") is None


def test_format_helpers():
    assert "ago" in format_age(parse_timestamp("2020-01-01T00:00:00Z"))
    assert format_dt(None) == "—"
    dt = datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc)
    assert "2025-01-01" in format_dt(dt)


def test_make_table_basic():
    t = make_table("Test", ["A", "B"])
    assert t is not None


def test_skill_template_and_validate():
    md = skill_template("test-skill", "Does amazing things for testing")
    assert "name: test-skill" in md
    assert "description: Does amazing things for testing" in md

    with tempfile.TemporaryDirectory() as td:
        d = Path(td) / "test-skill"
        d.mkdir()
        (d / "SKILL.md").write_text(md)
        s = parse_skill(d)
        assert s is not None
        assert s.name == "test-skill"
        assert not validate_skill(s)  # should be valid enough


def test_validate_bad_skill():
    s = Skill(name="", description="short", path=Path("."), content="tiny")
    errs = validate_skill(s)
    assert len(errs) >= 2


def test_iter_sessions_empty(tmp_path: Path):
    # No sessions dir -> empty
    grok = tmp_path / ".grok"
    sessions = list(iter_sessions(grok))
    assert sessions == []


def test_iter_sessions_with_fake_summary(tmp_path: Path):
    grok = tmp_path / ".grok"
    sess_dir = grok / "sessions" / "proj-123" / "019e87abc"
    sess_dir.mkdir(parents=True)
    summary = {
        "info": {"id": "019e87abc", "cwd": "/tmp/proj"},
        "created_at": "2026-05-01T10:00:00Z",
        "last_active_at": "2026-05-02T11:00:00Z",
        "num_messages": 42,
        "num_chat_messages": 30,
        "current_model_id": "grok-3",
        "agent_name": "coder",
        "session_summary": "Did some work on auth",
    }
    (sess_dir / "summary.json").write_text(json.dumps(summary))

    sessions = list(iter_sessions(grok))
    assert len(sessions) == 1
    s = sessions[0]
    assert isinstance(s, SessionSummary)
    assert s.id == "019e87abc"
    assert s.cwd == "/tmp/proj"
    assert s.num_messages == 42
    assert s.current_model_id == "grok-3"


def test_load_session_updates_and_count(tmp_path: Path):
    sess_dir = tmp_path / "sess"
    sess_dir.mkdir()
    upd = sess_dir / "updates.jsonl"
    upd.write_text(
        '{"params":{"update":{"sessionUpdate":"tool_call","title":"read_file"}}}\n'
        '{"params":{"update":{"toolCall":"something"}}}\n'
    )
    updates = load_session_updates(sess_dir)
    assert len(updates) == 2
    counts = count_tool_calls(updates)
    assert counts.get("read_file", 0) >= 1


def test_safe_extract_tar_good(tmp_path: Path):
    # Create a good tar
    tar_path = tmp_path / "good.tar.gz"
    with tarfile.open(tar_path, "w:gz") as tar:
        info = tarfile.TarInfo(name="safe-dir/README.md")
        info.size = 0
        tar.addfile(info, fileobj=None)

    extract_to = tmp_path / "out"
    with tarfile.open(tar_path, "r:gz") as tar:
        safe_extract_tar(tar, extract_to)

    assert (extract_to / "safe-dir" / "README.md").exists()


def test_safe_extract_tar_blocks_traversal(tmp_path: Path):
    tar_path = tmp_path / "evil.tar.gz"
    with tarfile.open(tar_path, "w:gz") as tar:
        # classic zip slip
        evil = tarfile.TarInfo(name="../../../etc/passwd")
        evil.size = 0
        tar.addfile(evil)

    extract_to = tmp_path / "out2"
    with tarfile.open(tar_path, "r:gz") as tar:
        with pytest.raises(RuntimeError, match="traversal"):
            safe_extract_tar(tar, extract_to)

    # nothing should have been written outside
    assert not (tmp_path / "etc").exists()


def test_parse_age_delta():
    from datetime import timedelta

    from grok_build_cli_utilities.utils.common import parse_age_delta

    assert parse_age_delta("30d") == timedelta(days=30)
    assert parse_age_delta("2w") == timedelta(weeks=2)
    assert parse_age_delta("6mo").days == 180
    assert parse_age_delta("1y").days == 365
    assert parse_age_delta("48h") == timedelta(hours=48)
    assert parse_age_delta("7") == timedelta(days=7)
    # bad input falls back to 90d
    assert parse_age_delta("nonsense") == timedelta(days=90)
