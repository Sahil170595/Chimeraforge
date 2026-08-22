"""Tests for the CLI and MCP input/output contracts.

Batch E of an adversarial review. These are the two doors into the tool, and
both leaked in the same direction: input that should have been rejected was
accepted, and output that had to be machine-readable was not.

The sharpest one is that `--json` payloads were printed through Rich's markup
parser. Square brackets are style tags to Rich, so a model id containing them
had text silently deleted, produced invalid escapes, or raised MarkupError --
on the one output whose entire contract is being valid JSON. Model ids arrive
from the HF Hub and from MCP callers, not just from a keyboard.
"""

from __future__ import annotations

import json

import pytest

from chimeraforge.mcp_server import plan_deployment
from chimeraforge.planner.service import validate_plan_inputs


def _cli(*args):
    from typer.testing import CliRunner

    from chimeraforge.cli import app

    return CliRunner().invoke(app, list(args))


def _manual_model(ident: str) -> list[str]:
    """Plan an arbitrary id offline, so the id itself is the only variable."""
    return [
        "plan",
        "--model",
        ident,
        "--params-b",
        "7",
        "--n-layers",
        "32",
        "--n-kv-heads",
        "8",
        "--d-head",
        "128",
        "--no-network",
        "--budget",
        "1e9",
        "--quality-target",
        "0",
    ]


class TestJsonSurvivesRichMarkup:
    @pytest.mark.parametrize(
        "ident",
        [
            "org/x[bold]y-7b",  # a tag Rich recognises -> text deleted
            "org/[bracket]-model",  # produced an invalid JSON escape
            "org/x[/bold]y-7b",  # a closing tag -> raised MarkupError
            "org/plain-7b",  # control
        ],
    )
    def test_the_id_round_trips_verbatim(self, ident):
        r = _cli(*_manual_model(ident), "--json")
        assert r.exit_code == 0, r.output
        data = json.loads(r.output[r.output.index("[") : r.output.rindex("]") + 1])
        assert data[0]["model"] == ident

    def test_a_bracketed_id_does_not_crash_the_error_path(self):
        r = _cli("plan", "--model", "org/x[/bold]y", "--no-network", "--json")
        # Either a clean plan or a clean JSON error -- never a traceback.
        assert "Traceback" not in r.output
        assert "MarkupError" not in r.output

    def test_default_json_is_still_a_bare_array(self):
        r = _cli("plan", "--model-size", "3b", "--json")
        assert r.exit_code == 0
        assert isinstance(
            json.loads(r.output[r.output.index("[") : r.output.rindex("]") + 1]), list
        )


class TestDegreeParsing:
    @pytest.mark.parametrize("bad", ["1_0", "0x10", "1e1", "+4", "abc", "-1", "0"])
    def test_rejects_anything_that_is_not_plain_digits(self, bad):
        """Bare int() accepts Python numeric underscores, so `--tp 1_0` silently
        became a ten-way shard."""
        r = _cli("plan", "--model-size", "3b", "--tp", bad, "--budget", "1e9", "--json")
        assert r.exit_code == 1, f"--tp {bad!r} was accepted"

    @pytest.mark.parametrize("good", ["1", "4", " 2 ", "auto", "AUTO"])
    def test_accepts_valid_degrees(self, good):
        r = _cli("plan", "--model-size", "3b", "--tp", good, "--budget", "1e9", "--json")
        assert r.exit_code == 0, r.output


class TestSharedInputValidation:
    """The CLI validated and the MCP tool did not, so the surface an LLM drives
    was the unguarded one."""

    @pytest.mark.parametrize(
        "kwargs,fragment",
        [
            ({"kv_quant": "q3"}, "kv_quant"),
            ({"request_rate": -1.0}, "request_rate"),
            ({"request_rate": 0.0}, "request_rate"),
            ({"avg_output_tokens": 0}, "avg_output_tokens"),
            ({"prompt_tokens": -5}, "prompt_tokens"),
            ({"reasoning_tokens": -1}, "reasoning_tokens"),
            ({"duty_cycle": 0.0}, "duty_cycle"),
            ({"duty_cycle": 1.5}, "duty_cycle"),
            ({"prefix_cache_hit_rate": 2.0}, "prefix_cache_hit_rate"),
            ({"gpu_price_multiplier": 0.0}, "gpu_price_multiplier"),
            ({"ttft_slo_ms": 0.0}, "ttft_slo"),
            ({"latency_slo_ms": 0.0}, "latency_slo"),
            ({"context_length": 0}, "context_length"),
        ],
    )
    def test_mcp_rejects_rather_than_crashing_or_clamping(self, kwargs, fragment):
        r = plan_deployment(hardware="RTX 4090 24GB", **kwargs)
        assert r["ok"] is False, f"{kwargs} was accepted"
        assert fragment in r["error"]

    def test_valid_input_still_plans(self):
        r = plan_deployment(
            hardware="RTX 4090 24GB", model_size="8b", request_rate=2.0, budget_usd_month=5000
        )
        assert r["ok"] and r["recommended"]

    def test_run_plan_itself_still_clamps_for_library_callers(self):
        """Deliberate split: the engine clamps so a direct library caller cannot
        produce nonsense; the user-facing entry points reject first. Validating
        inside run_plan would break that contract, which other tests pin."""
        from chimeraforge.planner.service import run_plan

        cand = run_plan(
            model_size="3b", hardware="RTX 4090 24GB", budget=1e9, duty_cycle=5.0
        ).candidates[0]
        assert cand.duty_cycle == 1.0

    def test_the_validator_is_not_wired_into_run_plan(self):
        import inspect

        from chimeraforge.planner import service

        assert "validate_plan_inputs" not in inspect.getsource(service.run_plan)

    def test_valid_edges_are_allowed(self):
        validate_plan_inputs(
            request_rate=0.001,
            avg_tokens=1,
            reasoning_tokens=0,
            prompt_tokens=1,
            prefix_cache_hit_rate=1.0,
            duty_cycle=1.0,
            gpu_price_multiplier=0.001,
            host_bandwidth_gbps=None,
            ttft_slo=None,
            tpot_slo=None,
            electricity_rate=0.0,
            kv_quant="FP16",
            latency_slo=1.0,
            context_length=1,
        )


class TestMcpEnvelopeIsStable:
    def test_both_outcomes_have_identical_keys(self):
        feasible = plan_deployment(
            hardware="RTX 4090 24GB", model_size="8b", request_rate=2.0, budget_usd_month=5000
        )
        infeasible = plan_deployment(
            hardware="RTX 4090 24GB", model_size="8b", budget_usd_month=0.0001
        )
        assert sorted(feasible) == sorted(infeasible)

    def test_no_fit_uses_null_not_a_missing_key(self):
        r = plan_deployment(hardware="RTX 4090 24GB", model_size="8b", budget_usd_month=0.0001)
        assert r["recommended"] is None
        assert r["alternatives"] == []

    def test_why_nothing_fit_is_always_a_list(self):
        for kwargs in ({"budget_usd_month": 0.0001}, {"budget_usd_month": 5000}):
            r = plan_deployment(hardware="RTX 4090 24GB", model_size="8b", **kwargs)
            assert isinstance(r["why_nothing_fit"], list)

    def test_the_duty_corrected_cost_is_reported(self):
        """The at-capacity figure assumes a saturated fleet; below 100% duty you
        also pay for every idle hour, and that is what people budget against."""
        r = plan_deployment(
            hardware="RTX 4090 24GB",
            model_size="8b",
            request_rate=2.0,
            budget_usd_month=5000,
            duty_cycle=0.3,
        )
        rec = r["recommended"]
        assert rec["duty_cycle"] == pytest.approx(0.3)
        assert rec["cost_per_1m_tok_effective_usd"] > rec["cost_per_1m_tok_usd"]


class TestValidateFlagCombination:
    def test_measurements_plus_ollama_url_is_refused(self, tmp_path):
        """Resolving this silently scored a stale file while the operator believed
        a fresh benchmark had run -- and exited 0."""
        matrix = tmp_path / "m.json"
        matrix.write_text(json.dumps({"registered_at": "2026-01-01", "cells": []}), "utf-8")
        meas = tmp_path / "cap.json"
        meas.write_text("{}", encoding="utf-8")
        r = _cli(
            "validate",
            "--matrix",
            str(matrix),
            "--measurements",
            str(meas),
            "--ollama-url",
            "http://localhost:11434",
        )
        assert r.exit_code == 1
        assert "mutually exclusive" in r.output


class TestWorkloadProfileFailsLoud:
    def test_malformed_field_raises_workload_error_not_key_error(self, tmp_path):
        from chimeraforge.workload import WorkloadError, WorkloadProfile

        p = tmp_path / "bad.json"
        p.write_text(
            json.dumps(
                {"schema_version": 1, "fields": {"request_rate": {"provenance": "measured"}}}
            ),
            encoding="utf-8",
        )
        with pytest.raises(WorkloadError, match="malformed"):
            WorkloadProfile.load(p)

    def test_the_cli_reports_it_without_a_traceback(self, tmp_path):
        p = tmp_path / "bad.json"
        p.write_text(
            json.dumps({"schema_version": 1, "fields": {"request_rate": {"value": "abc"}}}),
            encoding="utf-8",
        )
        r = _cli("plan", "--model-size", "3b", "--workload-profile", str(p))
        assert r.exit_code == 1
        assert "Traceback" not in r.output

    def test_absent_provenance_is_unknown_not_estimated(self, tmp_path):
        """Defaulting to 'estimated' claimed more than the file actually said."""
        from chimeraforge.workload import WorkloadProfile

        p = tmp_path / "bare.json"
        p.write_text(
            json.dumps({"schema_version": 1, "fields": {"request_rate": {"value": 2.0}}}),
            encoding="utf-8",
        )
        assert WorkloadProfile.load(p).request_rate.provenance == "unknown"


class TestRefitStdoutIsOneDocument:
    def test_json_mode_does_not_emit_two_objects(self):
        """`--json --validate` printed the summary and then the validation report,
        producing two concatenated JSON documents that no parser accepts."""
        import inspect

        from chimeraforge.commands import refit as refit_cmd

        src = inspect.getsource(refit_cmd)
        assert "err_console" in src
        # The trailing validation dump must go to stderr.
        assert "err_console.print(\n                format_validation_json" in src or (
            "err_console.print(format_validation_json" in src
        )

    def test_errors_go_to_stderr(self):
        import inspect

        from chimeraforge.commands import refit as refit_cmd

        import re

        src = inspect.getsource(refit_cmd)
        # Negative lookbehind: "err_console.print" contains "console.print", so a
        # plain substring check passes on the very code it is meant to reject.
        stray = re.findall(r'(?<!err_)console\.print\(f?"\[red\]', src)
        assert not stray, f"{len(stray)} error(s) still printed to stdout"
