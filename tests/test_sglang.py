"""Tests for the SGLang backend.

The load-bearing property is negative: SGLang ships with NO measured rows, so it
must predict from first principles and say so. Cloning vLLM's coefficients would
have made the numbers look confident and been a lie -- these tests exist to stop
that happening later by accident.
"""

from __future__ import annotations

import pytest

from chimeraforge.planner.constants import (
    BACKEND_CONTINUOUS_BATCHING,
    BACKENDS,
    backend_supports_quant,
)
from chimeraforge.planner.launch import build_launch_command
from chimeraforge.planner.models import load_bundled_models
from chimeraforge.planner.service import run_plan


@pytest.fixture(scope="module")
def models():
    return load_bundled_models()


@pytest.fixture(scope="module")
def plan():
    return run_plan(
        model_size="8b",
        hardware="H100 80GB",
        request_rate=2.0,
        budget=1e9,
        quality_target=0.0,
        latency_slo=60000,
    )


def _sglang(plan):
    return [c for c in plan.candidates if c.backend == "sglang"]


class TestRegistration:
    def test_sglang_is_a_backend(self):
        assert "sglang" in BACKENDS

    def test_it_batches_continuously(self):
        assert BACKEND_CONTINUOUS_BATCHING["sglang"] is True

    def test_it_serves_float_and_fp8_not_gguf(self):
        assert backend_supports_quant("sglang", "FP16")
        assert backend_supports_quant("sglang", "FP8")
        assert not backend_supports_quant("sglang", "Q4_K_M")

    def test_it_appears_in_a_plan(self, plan):
        assert _sglang(plan)


class TestNoBorrowedNumbers:
    """The whole point: an unmeasured backend must not inherit a measured one's data."""

    def test_corpus_has_no_sglang_rows(self, models):
        assert not models.throughput.has_measured_rows("sglang")

    def test_measured_backends_still_report_measured(self, models):
        for backend in ("ollama", "vllm", "tgi"):
            assert models.throughput.has_measured_rows(backend)

    def test_provenance_is_never_measured(self, plan):
        for c in _sglang(plan):
            assert c.provenance["throughput"] != "measured"

    def test_it_says_so_in_a_warning(self, plan):
        w = [x for c in _sglang(plan) for x in c.warnings if "sglang has no measured rows" in x]
        assert w and "NOT borrowed" in w[0]

    def test_measured_backends_get_no_such_warning(self, plan):
        for c in plan.candidates:
            if c.backend != "sglang":
                assert not any("no measured rows" in x for x in c.warnings)

    def test_throughput_is_not_a_copy_of_vllm(self, models):
        """On a model vLLM HAS been measured on, SGLang must not report that number.

        Uses llama3.2-1b deliberately: the corpus holds `llama3.2-1b|vllm|FP16`, so
        vLLM answers from a measurement while SGLang has nothing to answer from. If
        someone ever wires SGLang to vLLM's lookup, these converge and this fails.
        (An 8B would not catch it -- the corpus has no rows for it on any backend,
        so both legitimately fall to the same power-law.)
        """
        assert "llama3.2-1b|vllm|FP16" in models.throughput.lookup
        assert "llama3.2-1b|sglang|FP16" not in models.throughput.lookup
        vllm = models.throughput.predict("llama3.2-1b", "vllm", "FP16", "H100 80GB")
        sglang = models.throughput.predict("llama3.2-1b", "sglang", "FP16", "H100 80GB")
        assert vllm != sglang, "SGLang is reporting vLLM's measured throughput"

    def test_unmeasured_backends_share_the_same_first_principles_estimate(self, models):
        """Two unmeasured backends agreeing is correct, not a bug.

        Pinned so the test above is not misread as 'these must always differ': on a
        model nobody has measured, every unmeasured backend lands on the same
        power-law, and that is the honest answer rather than invented spread.
        """
        assert not any(k.startswith("llama3.1-8b|") for k in models.throughput.lookup)
        a = models.throughput.predict("llama3.1-8b", "sglang", "FP16", "H100 80GB")
        b = models.throughput.predict("llama3.1-8b", "vllm", "FP16", "H100 80GB")
        assert a == b


class TestLaunchCommand:
    def _cmd(self, plan, **kw):
        return build_launch_command(_sglang(plan)[0], None, **kw)

    def test_uses_the_real_launcher(self, plan):
        lc = self._cmd(plan, context_length=8192)
        assert lc.backend == "sglang"
        assert lc.command.startswith("python -m sglang.launch_server --model-path")

    def test_carries_the_planned_context_and_port(self, plan):
        cmd = self._cmd(plan, context_length=8192).command
        assert "--context-length 8192" in cmd and "--port 30000" in cmd

    def test_kv_quant_maps_to_fp8(self, plan):
        assert (
            "--kv-cache-dtype fp8_e5m2"
            in self._cmd(plan, context_length=2048, kv_quant="q8").command
        )

    def test_q4_kv_is_flagged_as_coarser_in_reality(self, plan):
        lc = self._cmd(plan, context_length=2048, kv_quant="q4")
        assert any("smallest KV-cache dtype is fp8" in n for n in lc.notes)

    def test_tp_uses_sglang_flag_names(self):
        from chimeraforge.planner.engine import Candidate

        c = Candidate(
            model="org/m",
            quant="FP8",
            backend="sglang",
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
            tensor_parallel=4,
            effective_batch=8,
        )
        cmd = build_launch_command(c, None, context_length=4096).command
        assert "--tp-size 4" in cmd
        assert "--max-running-requests 8" in cmd
        assert "--quantization fp8" in cmd


def test_other_backends_are_unchanged(plan):
    # SGLang is additive: the existing backends must still be offered.
    assert {"ollama", "vllm", "tgi"} <= {c.backend for c in plan.candidates}
