"""Tests for the CLI plan command and formatter output."""

from __future__ import annotations

import json

import pytest

from chimeraforge.planner.engine import Candidate, enumerate_candidates


# -- CLI Integration ----------------------------------------------------------


class TestCLIPlan:
    @pytest.mark.parametrize("measure_first", [False, True])
    @pytest.mark.parametrize(
        ("option", "value"),
        [
            ("--request-rate", "nan"),
            ("--electricity-rate", "nan"),
            ("--gpu-price-multiplier", "inf"),
            ("--ttft-slo", "inf"),
        ],
    )
    def test_nonfinite_plans_fail_before_search_in_either_output_mode(
        self, monkeypatch, option, value, measure_first
    ):
        from typer.testing import CliRunner

        from chimeraforge import measure
        from chimeraforge.cli import app
        from chimeraforge.planner import service

        def unexpected_search(**kwargs):
            pytest.fail("planner began search for a non-finite request")

        async def unexpected_measurement(*args, **kwargs):
            pytest.fail("planner began measurement for a non-finite request")

        monkeypatch.setattr(service, "run_plan", unexpected_search)
        monkeypatch.setattr(measure, "measure_model", unexpected_measurement)
        args = ["plan", "--model", "fixture/off-registry", option, value]
        if measure_first:
            args.append("--measure")
        runner = CliRunner()
        summary = runner.invoke(app, args)
        structured = runner.invoke(app, [*args, "--json"])
        assert summary.exit_code == structured.exit_code == 1
        assert "finite" in summary.output and "finite" in json.loads(structured.stdout)["error"]

    @pytest.mark.parametrize(
        ("options", "message"),
        [
            (["--lora-adapters", "1", "--lora-target", "bogus"], "unknown lora_target"),
            (["--lora-adapters", "100000", "--lora-rank", "16"], "adapter ceiling"),
            (["--lora-adapters", "1", "--lora-rank", "100000"], "lora_rank must be between"),
            (
                ["--fleet", "H100 80GB,RTX 4090 24GB", "--save", "unused.json"],
                "heterogeneous fleets",
            ),
        ],
    )
    def test_invalid_plan_options_refuse_before_measurement(self, monkeypatch, options, message):
        from typer.testing import CliRunner

        from chimeraforge import measure
        from chimeraforge.cli import app
        from chimeraforge.planner import service

        async def unexpected_measurement(*args, **kwargs):
            pytest.fail("planner began measurement before rejecting invalid options")

        def unexpected_search(**kwargs):
            pytest.fail("planner began search before rejecting invalid options")

        monkeypatch.setattr(measure, "measure_model", unexpected_measurement)
        monkeypatch.setattr(service, "run_plan", unexpected_search)
        result = CliRunner().invoke(
            app, ["plan", "--model", "llama3.2-3b", "--measure", "--no-network", *options, "--json"]
        )
        assert result.exit_code == 1
        assert message in json.loads(result.stdout)["error"]

    def test_valid_measurement_still_runs_before_search_and_has_clean_json(self, monkeypatch):
        from types import SimpleNamespace

        from typer.testing import CliRunner

        from chimeraforge import measure
        from chimeraforge.cli import app
        from chimeraforge.planner import service

        stages = []
        original_plan = service.run_plan

        async def measured(model, **kwargs):
            stages.append("measure")
            assert model == "llama3.2-3b" and kwargs["backend"] == "ollama"
            return SimpleNamespace(tps_n1=50, n_concurrent=1, eta_at_n=None)

        def ordered_search(**kwargs):
            stages.append("plan")
            return original_plan(**kwargs)

        monkeypatch.setattr(measure, "measure_model", measured)
        monkeypatch.setattr(service, "run_plan", ordered_search)
        result = CliRunner().invoke(
            app,
            [
                "plan",
                "--model",
                "llama3.2-3b",
                "--measure",
                "--no-network",
                "--request-rate",
                "0.01",
                "--json",
            ],
        )
        assert result.exit_code == 0, result.output
        assert stages == ["measure", "plan"]
        assert json.loads(result.stdout) and "Measured" in result.stderr

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

    def test_plan_help_lists_model_flag(self):
        from typer.testing import CliRunner
        from chimeraforge.cli import app

        runner = CliRunner()
        result = runner.invoke(app, ["plan", "--help"])
        assert "--model" in self._strip_ansi(result.output)

    def test_plan_offregistry_manual_override_json(self):
        from typer.testing import CliRunner
        from chimeraforge.cli import app

        runner = CliRunner()
        result = runner.invoke(
            app,
            [
                "plan",
                "--model",
                "mystery/model-7b",
                "--params-b",
                "7.0",
                "--n-layers",
                "32",
                "--n-kv-heads",
                "8",
                "--d-head",
                "128",
                "--no-network",
                "--quality-target",
                "0",
                "--budget",
                "1000",
                "--hardware",
                "RTX 4090 24GB",
                "--json",
            ],
        )
        assert result.exit_code == 0
        data = self._extract_json(result.output)
        assert data
        c = data[0]
        assert c["model"] == "mystery/model-7b"
        assert c["params_b"] == 7.0
        assert c["model_source"] == "manual"
        assert c["provenance"]["throughput"] == "estimated"
        assert c["provenance"]["safety"] == "unknown"

    def test_plan_pareto(self):
        from typer.testing import CliRunner

        from chimeraforge.cli import app

        result = CliRunner().invoke(app, ["plan", "--pareto", "--quality-target", "0"])
        assert result.exit_code == 0
        assert "frontier" in self._strip_ansi(result.output).lower()

    def test_plan_pareto_json(self):
        from typer.testing import CliRunner

        from chimeraforge.cli import app

        result = CliRunner().invoke(app, ["plan", "--pareto", "--json", "--quality-target", "0"])
        assert result.exit_code == 0
        data = self._extract_json(result.output)
        assert isinstance(data, list) and data

    def test_plan_workload_agent_accepted(self):
        from typer.testing import CliRunner

        from chimeraforge.cli import app

        result = CliRunner().invoke(app, ["plan", "--workload", "agent", "--quality-target", "0"])
        assert result.exit_code == 0

    def test_plan_bad_workload_rejected(self):
        from typer.testing import CliRunner

        from chimeraforge.cli import app

        result = CliRunner().invoke(app, ["plan", "--workload", "bogus"])
        assert result.exit_code == 1

    def test_plan_overrides_require_single_model(self):
        from typer.testing import CliRunner
        from chimeraforge.cli import app

        runner = CliRunner()
        result = runner.invoke(
            app,
            ["plan", "--model", "a/b", "--model", "c/d", "--params-b", "7.0"],
        )
        assert result.exit_code == 1

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
