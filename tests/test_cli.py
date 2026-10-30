"""Tests for the Phalanx CLI commands."""

from click.testing import CliRunner
from phalanx.cli import main


def test_cli_personas():
    runner = CliRunner()
    result = runner.invoke(main, ["personas"])
    assert result.exit_code == 0
    assert "fake-ceo" in result.output
    assert "panicked-grandma" in result.output


def test_cli_scenarios():
    runner = CliRunner()
    result = runner.invoke(main, ["scenarios"])
    assert result.exit_code == 0
    assert "acme-roofing-bec" in result.output


def test_cli_leaderboard():
    runner = CliRunner()
    result = runner.invoke(main, ["leaderboard"])
    assert result.exit_code == 0
    assert "Target Defense Robustness" in result.output


def test_cli_vault():
    runner = CliRunner()
    result = runner.invoke(main, ["vault"])
    assert result.exit_code == 0
    assert "PHALANX Regression Vault" in result.output
