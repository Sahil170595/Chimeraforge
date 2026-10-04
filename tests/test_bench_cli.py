"""Tests for the bench CLI entry point (typer app)."""

from __future__ import annotations


# -- CLI integration ---------------------------------------------------------


class TestCLI:
    def test_bench_json_stdout_is_parseable_and_saved_output_agrees(self, monkeypatch, tmp_path):
        import json

        from typer.testing import CliRunner

        from chimeraforge.bench import runner as benchmark_runner
        from chimeraforge.bench.metrics import (
            BenchmarkResult,
            RunMetrics,
            aggregate_runs,
            collect_environment,
            now_iso,
        )
        from chimeraforge.cli import app

        measured = [RunMetrics(4, 4.0, 1.0, 1000.0, 20.0, 980.0)]
        benchmark = BenchmarkResult(
            "test",
            "ollama",
            None,
            "single",
            1,
            2048,
            measured,
            aggregate_runs(measured),
            collect_environment("ollama"),
            now_iso(),
        )

        async def run_benchmark(**kwargs):
            return benchmark

        monkeypatch.setattr(benchmark_runner, "run_benchmark", run_benchmark)
        result = CliRunner().invoke(
            app,
            ["bench", "--model", "test", "--runs", "1", "--json", "--output-dir", str(tmp_path)],
        )
        assert result.exit_code == 0
        payload = json.loads(result.stdout)
        saved = list(tmp_path.glob("bench_*.json"))
        assert len(saved) == 1
        assert payload == json.loads(saved[0].read_text(encoding="utf-8"))
        assert "Results saved to:" in result.stderr

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
