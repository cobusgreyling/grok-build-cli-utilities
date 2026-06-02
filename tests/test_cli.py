"""Smoke tests for the CLI entrypoint."""

from typer.testing import CliRunner

from grok_build_cli_utilities.cli import app

runner = CliRunner()


def test_help():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "grok-utils" in result.output
    assert "sessions" in result.output
    assert "skills" in result.output


def test_version():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "0.1.0" in result.output


def test_sessions_help():
    result = runner.invoke(app, ["sessions", "--help"])
    assert result.exit_code == 0
    assert "list" in result.output
    assert "search" in result.output


def test_skills_help():
    result = runner.invoke(app, ["skills", "--help"])
    assert result.exit_code == 0
