"""Tests for the bench CLI entry point (typer app)."""

from __future__ import annotations


# -- CLI integration ---------------------------------------------------------


class TestCLI:
    @staticmethod
    def _strip_ansi(text: str) -> str:
        import re

        return re.sub(r"\x1b\[[0-9;]*m", "", text)

    def test_bench_help(self):
        from typer.testing import CliRunner
        from chimeraforge.cli import app

        runner = CliRunner()
        result = runner.invoke(app, ["bench", "--help"])
        output = self._strip_ansi(result.output)
        assert result.exit_code == 0
        assert "--model" in output
        assert "--backend" in output
        assert "--workload" in output
        assert "--runs" in output

    def test_bench_requires_model(self):
        from typer.testing import CliRunner
        from chimeraforge.cli import app

        runner = CliRunner()
        result = runner.invoke(app, ["bench"])
        # Typer shows error for missing required option
        assert result.exit_code != 0

    def test_bench_invalid_context(self):
        from typer.testing import CliRunner
        from chimeraforge.cli import app

        runner = CliRunner()
        result = runner.invoke(app, ["bench", "--model", "test", "--context", "abc"])
        assert result.exit_code == 1

    def test_bench_negative_runs(self):
        from typer.testing import CliRunner
        from chimeraforge.cli import app

        runner = CliRunner()
        result = runner.invoke(app, ["bench", "--model", "test", "--runs", "0"])
        assert result.exit_code == 1

    def test_bench_negative_rate(self):
        from typer.testing import CliRunner
        from chimeraforge.cli import app

        runner = CliRunner()
        result = runner.invoke(app, ["bench", "--model", "test", "--rate", "-1"])
        assert result.exit_code == 1
