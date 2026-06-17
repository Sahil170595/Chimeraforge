"""Tests for the CLI plan command and formatter output."""

from __future__ import annotations

import json


from chimeraforge.planner.engine import Candidate, enumerate_candidates


# -- CLI Integration ----------------------------------------------------------


class TestCLIPlan:
    @staticmethod
    def _strip_ansi(text: str) -> str:
        import re

        return re.sub(r"\x1b\[[0-9;]*m", "", text)

    def test_plan_help(self):
        from typer.testing import CliRunner
        from chimeraforge.cli import app

        runner = CliRunner()
        result = runner.invoke(app, ["plan", "--help"])
        output = self._strip_ansi(result.output)
        assert result.exit_code == 0
        assert "--model-size" in output

    def test_plan_negative_request_rate(self):
        from typer.testing import CliRunner
        from chimeraforge.cli import app

        runner = CliRunner()
        result = runner.invoke(app, ["plan", "--request-rate", "-1"])
        assert result.exit_code == 1

    def test_plan_zero_avg_tokens(self):
        from typer.testing import CliRunner
        from chimeraforge.cli import app

        runner = CliRunner()
        result = runner.invoke(app, ["plan", "--avg-tokens", "0"])
        assert result.exit_code == 1

    def test_plan_invalid_quality_target(self):
        from typer.testing import CliRunner
        from chimeraforge.cli import app

        runner = CliRunner()
        result = runner.invoke(app, ["plan", "--quality-target", "1.5"])
        assert result.exit_code == 1

    def test_plan_json_output(self):
        from typer.testing import CliRunner
        from chimeraforge.cli import app

        runner = CliRunner()
        result = runner.invoke(app, ["plan", "--json"])
        assert result.exit_code == 0

    def _extract_json(self, output: str):
        text = self._strip_ansi(output)
        return json.loads(text[text.index("[") : text.rindex("]") + 1])

    def test_plan_invalid_safety_target(self):
        from typer.testing import CliRunner
        from chimeraforge.cli import app

        runner = CliRunner()
        result = runner.invoke(app, ["plan", "--safety-target", "1.5"])
        assert result.exit_code == 1

    def test_plan_safety_target_accepted(self):
        from typer.testing import CliRunner
        from chimeraforge.cli import app

        runner = CliRunner()
        result = runner.invoke(app, ["plan", "--safety-target", "0.8"])
        assert result.exit_code == 0

    def test_plan_json_includes_safety_fields(self):
        from typer.testing import CliRunner
        from chimeraforge.cli import app

        runner = CliRunner()
        result = runner.invoke(app, ["plan", "--json"])
        data = self._extract_json(result.output)
        assert data
        assert "safety_refusal" in data[0]
        assert "rtsi_risk" in data[0]

    def test_plan_safety_filters_collapse_cell(self):
        from typer.testing import CliRunner
        from chimeraforge.cli import app

        runner = CliRunner()
        result = runner.invoke(
            app,
            [
                "plan",
                "--model-size",
                "1b",
                "--quality-target",
                "0",
                "--safety-target",
                "0.8",
                "--json",
            ],
        )
        data = self._extract_json(result.output)
        pairs = {(c["model"], c["quant"]) for c in data}
        assert ("llama3.2-1b", "Q2_K") not in pairs  # refusal 0.368 < 0.8
        assert ("llama3.2-1b", "Q4_K_M") in pairs  # refusal 0.905 >= 0.8


# -- Formatter ----------------------------------------------------------------


class TestFormatter:
    def test_format_json_all_fields(self, bundled_models):
        from dataclasses import fields
        from chimeraforge.planner.formatter import format_json

        candidates = enumerate_candidates(
            models=bundled_models,
            target_models=["llama3.2-3b"],
            hardware="RTX 4080 12GB",
            request_rate=0.5,
            latency_slo=10000,
            quality_target=0.3,
            budget=200,
            avg_tokens=128,
            context_length=2048,
        )
        raw = format_json(candidates)
        data = json.loads(raw)
        assert len(data) > 0
        # All Candidate fields present
        candidate_fields = {f.name for f in fields(Candidate)}
        assert candidate_fields == set(data[0].keys())

    def test_format_json_empty(self):
        from chimeraforge.planner.formatter import format_json

        raw = format_json([])
        assert json.loads(raw) == []
