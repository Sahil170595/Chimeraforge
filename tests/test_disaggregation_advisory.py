"""Tests for the prefill/decode disaggregation advisory.

The planner does not model disaggregation (roadmap D2: there is no closed-form
prefill:decode ratio, and vLLM's own docs say it "DOES NOT improve throughput").
What it can do honestly is say when a plan sits where the published sources say
disaggregation is worth considering, quote them, and predict nothing:

- both TTFT and TPOT are gated (DistServe's premise; vLLM's two stated uses);
- online serving (DistServe Sec. 7: for throughput-optimized offline work,
  chunked prefill "may be preferred");
- more than one GPU (DistServe Sec. 7: with "only a few or even a single GPU" the
  design space "is significantly limited");
- an engine whose own docs document it (vLLM v0.30.0, SGLang v0.5.20; TGI v3.3.7
  and Ollama do not).
"""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from chimeraforge.cli import app
from chimeraforge.planner.advisories import (
    DISAGG_ENGINE_DOCS,
    DISTSERVE,
    disaggregation_advisory,
)
from chimeraforge.planner.service import run_plan

ARGS = dict(
    backend="vllm",
    ttft_slo=1000.0,
    tpot_slo=80.0,
    gpus_total=4,
    batch_mode=False,
    ttft_ms=300.0,
    tpot_ms=25.0,
    decode_tokens=128,
    prompt_tokens=4096,
    interconnect_gbps=900.0,
    gpu_name="H100 80GB",
)


def _adv(**over):
    kw = dict(ARGS)
    kw.update(over)
    return disaggregation_advisory(**kw)


class TestWhenItApplies:
    def test_in_region(self):
        text = _adv()
        assert text.startswith("disaggregation advisory")

    @pytest.mark.parametrize(
        "over",
        [
            {"ttft_slo": None},
            {"tpot_slo": None},
            {"batch_mode": True},
            {"gpus_total": 1},
            {"backend": "tgi"},
            {"backend": "ollama"},
        ],
    )
    def test_outside_region_says_nothing(self, over):
        assert _adv(**over) == ""

    def test_both_documented_engines(self):
        assert set(DISAGG_ENGINE_DOCS) == {"vllm", "sglang"}
        assert _adv(backend="sglang")


class TestWhatItSays:
    def test_predicts_no_speedup_and_quotes_vllm(self):
        text = _adv()
        assert "No speedup is predicted" in text
        assert "DOES NOT improve throughput" in text
        assert "experimental" in text

    def test_cites_pinned_sources(self):
        text = _adv()
        assert "arXiv:2401.09670" in DISTSERVE and DISTSERVE in text
        assert DISAGG_ENGINE_DOCS["vllm"] in text
        assert "/v0.30.0/" in DISAGG_ENGINE_DOCS["vllm"]
        assert "/v0.5.20/" in DISAGG_ENGINE_DOCS["sglang"]

    def test_prefill_share_is_computed_from_the_plan(self):
        # 300 / (300 + 128 * 25) = 0.0857 -> 9%
        assert "prefill is 9% of a request's modeled service time" in _adv()

    def test_states_the_small_fleet_caveat_and_the_interconnect(self):
        text = _adv(gpus_total=2)
        assert "only a few or even a single GPU" in text
        assert "900 GB/s" in text
        assert "unknown" in _adv(interconnect_gbps=0.0)

    def test_names_chunked_prefill_as_the_alternative(self):
        assert "--max-num-batched-tokens" in _adv()


BASE = dict(
    model_size="8b",
    hardware="L4 24GB",
    request_rate=12.0,
    budget=1e9,
    quality_target=0.0,
    prompt_tokens=2048,
)


class TestPlan:
    def test_attached_to_qualifying_candidates_only(self):
        cands = run_plan(**BASE, ttft_slo=3000.0, tpot_slo=200.0).candidates
        assert cands
        for c in cands:
            expect = c.backend in ("vllm", "sglang") and c.gpus_total >= 2
            assert bool(c.disaggregation_advisory) == expect, (c.backend, c.gpus_total)
        assert any(c.disaggregation_advisory for c in cands)

    def test_absent_without_both_slos(self):
        for c in run_plan(**BASE, ttft_slo=3000.0).candidates:
            assert c.disaggregation_advisory == ""

    def test_cli_shows_it(self):
        r = CliRunner().invoke(
            app,
            [
                "plan",
                "--model-size",
                "8b",
                "--hardware",
                "L4 24GB",
                "--request-rate",
                "12",
                "--budget",
                "1000000000",
                "--quality-target",
                "0",
                "--prompt-tokens",
                "2048",
                "--ttft-slo",
                "3000",
                "--tpot-slo",
                "200",
                "--json",
            ],
        )
        assert r.exit_code == 0, r.output
        assert "disaggregation advisory" in r.output

    def test_mcp_carries_it(self):
        from chimeraforge.mcp_server import plan_deployment

        out = plan_deployment(
            model_size="8b",
            hardware="L4 24GB",
            request_rate=12.0,
            quality_target=0.0,
            prompt_tokens=2048,
            ttft_slo_ms=3000.0,
            tpot_slo_ms=200.0,
        )
        assert out["ok"], out
        rows = [out["recommended"], *out["alternatives"]]
        assert all("disaggregation_advisory" in r for r in rows)
