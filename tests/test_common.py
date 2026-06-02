"""Basic tests for shared utilities."""

from pathlib import Path
import tempfile

from grok_build_cli_utilities.utils.common import (
    get_grok_home,
    parse_timestamp,
    format_age,
    format_dt,
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


def test_parse_timestamp():
    assert parse_timestamp("2026-05-27T14:46:06.413248Z") is not None
    assert parse_timestamp(1716821166) is not None
    assert parse_timestamp(None) is None


def test_format_helpers():
    assert "ago" in format_age(parse_timestamp("2020-01-01T00:00:00Z"))
    assert format_dt(None) == "—"


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
