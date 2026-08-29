"""Tests for the remaining review findings: quoting, gates, and wrong strings.

Batch I. Mostly small, but two are not: a shell-injection surface in commands
the tool tells people to paste into a terminal, and a budget flag in my own
heterogeneous-fleet feature that simultaneously over- and under-constrained.

The string fixes are grouped here because they share a failure mode with the
larger ones -- a message that names a command or script which does not exist is
a small dishonesty, and it is the only recovery instruction the user gets.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from chimeraforge.planner.engine import Candidate
from chimeraforge.planner.fleet import FleetError, parse_fleet, plan_fleet
from chimeraforge.planner.launch import build_launch_command
from chimeraforge.planner.service import run_plan

ROOT = Path(__file__).resolve().parents[1]


def _cand(backend: str, model: str) -> Candidate:
    return Candidate(
        model=model,
        quant="FP16",
        backend=backend,
        n_agents=1,
        vram_gb=9.0,
        quality=0.8,
        quality_tier="negligible",
        throughput_tps=100.0,
        total_throughput_tps=100.0,
        eta=1.0,
        p95_latency_ms=500.0,
        utilisation=0.5,
        monthly_cost=25.0,
        cost_per_1m_tok=0.1,
        safety_refusal=None,
        rtsi_risk="UNKNOWN",
        warnings=[],
    )


class TestLaunchCommandsAreQuoted:
    """These commands are printed for a human to paste into a terminal, and model
    ids reach here from HF Hub listings and MCP callers -- not only from the
    keyboard of whoever runs it."""

    # ollama was omitted here while ollama was the one backend still interpolating
    # its tag raw -- and it wins the default plan for most registry queries, so it
    # is the most-emitted command, not an edge case.
    @pytest.mark.parametrize("backend", ["vllm", "sglang", "tgi", "ollama"])
    def test_command_substitution_is_neutralised(self, backend):
        cmd = build_launch_command(_cand(backend, "meta/x$(id)"), None, context_length=2048).command
        assert "$(id)" not in cmd or "'meta/x$(id)'" in cmd
        assert "meta/x$(id) " not in cmd, "the id is interpolated unquoted"

    @pytest.mark.parametrize(
        "hostile",
        ["meta/x;rm -rf /", "meta/x`id`", "meta/x&&whoami", "meta/x|tee /tmp/x"],
    )
    def test_shell_metacharacters_do_not_escape_the_argument(self, hostile):
        cmd = build_launch_command(_cand("vllm", hostile), None, context_length=2048).command
        # Everything after `vllm serve` up to the first line break must be one arg.
        arg = cmd.splitlines()[0].split("vllm serve", 1)[1].strip().rstrip(" \\")
        assert arg.startswith("'") and arg.endswith("'"), f"unquoted: {arg}"

    def test_ordinary_ids_are_not_uglified(self):
        cmd = build_launch_command(
            _cand("vllm", "Qwen/Qwen2.5-7B-Instruct"), None, context_length=2048
        ).command
        assert "vllm serve Qwen/Qwen2.5-7B-Instruct" in cmd

    def test_the_brief_already_did_this(self):
        """brief.py quotes its reproduction command; launch.py did not. Same rule,
        same reason."""
        from chimeraforge.planner.brief import BriefInputs

        assert "'RTX 4090 24GB'" in BriefInputs(hardware="RTX 4090 24GB").repro_command()


class TestFleetBudgetGatesTheMixNotEachGpu:
    """My own bug from the heterogeneous-fleet feature. Passing the budget into
    the per-GPU probe did both jobs badly at once."""

    KW = dict(
        model_size="3b",
        latency_slo=5000.0,
        quality_target=0.0,
        avg_tokens=128,
        context_length=2048,
    )

    def test_an_expensive_gpu_is_not_called_incapable(self):
        """An L4 at $360/mo was reported as "cannot serve this workload at all"
        against a small budget. It serves the workload perfectly well; it merely
        costs more than the cap. Per-unit affordability is not that question."""
        plan = plan_fleet(
            parse_fleet("RTX 4090 24GB,L4 24GB"),
            demand_rate=400.0,
            plan_fn=run_plan,
            plan_kwargs=dict(self.KW),
        )
        assert set(plan.options) == {"RTX 4090 24GB", "L4 24GB"}
        assert not any("cannot serve" in w for w in plan.warnings)

    def test_the_probe_is_unbudgeted_even_when_the_caller_passes_one(self):
        """run_plan's own default budget is $100/mo, so merely dropping the key
        still excluded anything dearer than that."""
        plan = plan_fleet(
            parse_fleet("RTX 4090 24GB,L4 24GB"),
            demand_rate=400.0,
            plan_fn=run_plan,
            plan_kwargs=dict(self.KW, budget=50.0),
        )
        assert "L4 24GB" in plan.options

    def test_an_over_budget_mix_is_refused_not_returned(self):
        """It used to return a $172.80 mix against a $100 budget and call it a
        plan."""
        with pytest.raises(FleetError, match="over the"):
            plan_fleet(
                parse_fleet("RTX 4090 24GB,L4 24GB"),
                demand_rate=400.0,
                plan_fn=run_plan,
                plan_kwargs=dict(self.KW),
                budget=100.0,
            )

    def test_an_affordable_mix_still_returns(self):
        plan = plan_fleet(
            parse_fleet("RTX 4090 24GB,L4 24GB"),
            demand_rate=400.0,
            plan_fn=run_plan,
            plan_kwargs=dict(self.KW),
            budget=1000.0,
        )
        assert plan.monthly_cost <= 1000.0

    def test_no_budget_means_no_gate(self):
        plan = plan_fleet(
            parse_fleet("RTX 4090 24GB"),
            demand_rate=400.0,
            plan_fn=run_plan,
            plan_kwargs=dict(self.KW),
        )
        assert plan.monthly_cost > 0


class TestPreRegistrationIsARealGate:
    def _matrix(self, tmp_path, quant="FP16"):
        m = tmp_path / "m.json"
        m.write_text(
            json.dumps(
                {
                    "registered_at": "2026-01-01",
                    "hardware": "RTX 4080 12GB",
                    "cells": [{"model": "llama3.2-3b", "backend": "ollama", "quant": quant}],
                }
            ),
            encoding="utf-8",
        )
        return m

    def _run(self, *args):
        from typer.testing import CliRunner

        from chimeraforge.cli import app

        return CliRunner().invoke(app, ["validate", *args])

    def test_matching_fingerprint_passes(self, tmp_path):
        from chimeraforge.validate import Matrix

        m = self._matrix(tmp_path)
        cap = tmp_path / "c.json"
        cap.write_text("{}", encoding="utf-8")
        fp = Matrix.load(m).fingerprint()
        r = self._run("--matrix", str(m), "--measurements", str(cap), "--expect-fingerprint", fp)
        assert r.exit_code == 0, r.output

    def test_an_edited_matrix_fails(self, tmp_path):
        """Without this the fingerprint was recomputed from whatever matrix was
        loaded and merely printed, so editing a cell after seeing results yielded a
        report that matched itself perfectly."""
        from chimeraforge.validate import Matrix

        original = Matrix.load(self._matrix(tmp_path)).fingerprint()
        edited = self._matrix(tmp_path, quant="Q4_K_M")
        assert Matrix.load(edited).fingerprint() != original, "precondition"
        cap = tmp_path / "c.json"
        cap.write_text("{}", encoding="utf-8")
        r = self._run(
            "--matrix",
            str(edited),
            "--measurements",
            str(cap),
            "--expect-fingerprint",
            original,
        )
        assert r.exit_code == 1
        assert "pre-registered" in r.output


class TestEngineRefusesUnknownHardware:
    def test_library_callers_get_an_error_not_a_12gb_substitute(self):
        """Both shipped callers pre-validate, but enumerate_candidates is exported
        public API and silently substituted a 12 GB card at $0.035/hr -- returning
        a full, confident result set for hardware nobody asked about."""
        from chimeraforge.planner.engine import enumerate_candidates
        from chimeraforge.planner.models import load_bundled_models

        with pytest.raises(ValueError, match="unknown GPU"):
            enumerate_candidates(
                models=load_bundled_models(),
                target_models=["llama3.2-3b"],
                hardware="RTX 6000 Ada 48GB",
                request_rate=1.0,
                latency_slo=5000.0,
                quality_target=0.0,
                budget=1e9,
                avg_tokens=128,
                context_length=2048,
            )

    def test_the_error_points_at_the_known_set(self):
        from chimeraforge.planner.engine import enumerate_candidates
        from chimeraforge.planner.models import load_bundled_models

        with pytest.raises(ValueError) as exc:
            enumerate_candidates(
                models=load_bundled_models(),
                target_models=["llama3.2-3b"],
                hardware="totally made up",
                request_rate=1.0,
                latency_slo=5000.0,
                quality_target=0.0,
                budget=1e9,
                avg_tokens=128,
                context_length=2048,
            )
        assert "GPU_DB" in str(exc.value)


class TestMessagesNameThingsThatExist:
    def test_no_source_string_suggests_the_invalid_catalog_invocation(self):
        """`chimeraforge catalog build` exits 2; the flag is `--build`. One of the
        three copies was in an MCP tool description handed to an LLM."""
        offenders = []
        for path in (ROOT / "src").rglob("*.py"):
            if "catalog build" in path.read_text(encoding="utf-8"):
                offenders.append(path.name)
        assert not offenders, f"invalid invocation still referenced in: {offenders}"

    def test_the_stale_price_refusal_names_a_real_script(self):
        from chimeraforge.planner.brief import STALE_REFUSAL

        assert "build_cost_data" in STALE_REFUSAL
        assert (ROOT / "scripts" / "build_cost_data.py").exists()

    def test_the_all_quants_help_matches_the_ladder(self):
        """It claimed 7 levels against a ladder of 10."""
        import inspect

        from chimeraforge.commands import bench as bench_cmd
        from chimeraforge.planner.constants import QUANT_LEVELS

        src = inspect.getsource(bench_cmd)
        assert "all 7 quantization" not in src
        assert len(QUANT_LEVELS) == 10

    def test_the_brief_budget_default_matches_the_cli(self):
        """They diverged (100000 vs 100), so an explicit --budget 100000 was
        treated as unchanged, omitted from the repro command, and the printed
        command re-ran at $100 producing a different plan from the brief."""
        import re

        from chimeraforge.planner.brief import BriefInputs

        src = (ROOT / "src" / "chimeraforge" / "commands" / "plan.py").read_text(encoding="utf-8")
        match = re.search(r"budget: float = typer\.Option\(\s*([0-9.]+)", src)
        assert match, "could not find the --budget default"
        assert BriefInputs(hardware="x").budget_usd_month == float(match.group(1))
