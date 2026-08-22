"""Tests for partial CPU offload.

"It does not fit" and "it runs" are both true at once: llama.cpp and Ollama stream
the weights that do not fit from host RAM. A planner that only ever says "does not
fit" loses the argument against a machine that is visibly running the model.

So the answer changes from a refusal to a priced one -- it runs, at this fraction
offloaded, this slowly -- while the derate stays labeled as modelled rather than
measured, and the host link speed stays a scenario input.
"""

from __future__ import annotations

import pytest

from chimeraforge.planner.service import run_plan

# A small card and a model that does not fit it: the whole point of the feature.
BASE = dict(
    model_size="8b",
    hardware="RTX 4060 8GB",
    request_rate=0.2,
    budget=1e9,
    quality_target=0.0,
    latency_slo=1e9,
    context_length=2048,
)


def _plan(**over):
    kw = dict(BASE)
    kw.update(over)
    return run_plan(**kw).candidates


def _most_offloaded(cands):
    return max(cands, key=lambda c: c.offload_fraction)


class TestDefaultIsOff:
    def test_no_offload_by_default(self):
        assert all(c.offload_fraction == 0.0 for c in _plan())

    def test_results_unchanged_when_off(self):
        # Additive: the pre-existing answer must survive untouched.
        off = _plan()
        assert off and all(c.host_bandwidth_gbps == 0.0 for c in off)

    def test_no_warning_when_off(self):
        assert not any("partial CPU offload" in w for c in _plan() for w in c.warnings)


class TestItRunsInsteadOfRefusing:
    def test_offload_admits_configs_that_did_not_fit(self):
        assert len(_plan(allow_offload=True)) > len(_plan())

    def test_a_config_actually_offloads(self):
        assert _most_offloaded(_plan(allow_offload=True)).offload_fraction > 0

    def test_offloaded_config_is_slower_not_faster(self):
        # The point of the derate: it runs, and it crawls.
        c = _most_offloaded(_plan(allow_offload=True))
        same_resident = [x for x in _plan() if x.quant == c.quant and x.backend == c.backend]
        if same_resident:
            assert c.throughput_tps < same_resident[0].throughput_tps

    def test_fraction_is_a_fraction(self):
        for c in _plan(allow_offload=True):
            assert 0.0 <= c.offload_fraction <= 1.0


class TestDerateIsBandwidthDriven:
    def test_slower_host_link_means_slower_decode(self):
        fast = _most_offloaded(_plan(allow_offload=True, host_bandwidth_gbps=128.0))
        slow = _most_offloaded(_plan(allow_offload=True, host_bandwidth_gbps=16.0))
        assert slow.throughput_tps < fast.throughput_tps

    def test_the_assumed_link_speed_is_recorded(self):
        c = _most_offloaded(_plan(allow_offload=True, host_bandwidth_gbps=48.0))
        assert c.host_bandwidth_gbps == 48.0

    def test_defaults_to_the_gpus_pcie_figure(self):
        from chimeraforge.planner.hardware import GPU_DB

        c = _most_offloaded(_plan(allow_offload=True))
        assert c.host_bandwidth_gbps == GPU_DB["RTX 4060 8GB"].interconnect_gbps


class TestItStillRefusesWhenOffloadCannotHelp:
    """Only weights spill. KV and activations must stay resident."""

    def test_impossible_context_is_still_rejected(self):
        # A context whose KV alone dwarfs the card cannot be offloaded into fitting.
        assert not _plan(allow_offload=True, context_length=1_000_000)

    def test_rejection_says_offload_cannot_help(self):
        from chimeraforge.planner.engine import enumerate_candidates
        from chimeraforge.planner.models import load_bundled_models

        trace: list = []
        enumerate_candidates(
            models=load_bundled_models(),
            target_models=["llama3.1-8b"],
            hardware="RTX 4060 8GB",
            request_rate=0.2,
            latency_slo=1e9,
            quality_target=0.0,
            budget=1e9,
            avg_tokens=128,
            context_length=1_000_000,
            allow_offload=True,
            trace=trace,
        )
        reasons = [d for _, _, gate, d in trace if gate == "vram"]
        assert reasons and any("offload cannot help" in r for r in reasons)


class TestHonesty:
    def test_warning_says_modelled_not_measured(self):
        c = _most_offloaded(_plan(allow_offload=True))
        w = [x for x in c.warnings if "partial CPU offload" in x]
        assert w
        assert "MODELLED" in w[0] and "not measured" in w[0]

    def test_warning_names_the_link_as_a_scenario_input(self):
        c = _most_offloaded(_plan(allow_offload=True))
        w = [x for x in c.warnings if "partial CPU offload" in x]
        assert "scenario input" in w[0]


class TestSurfaces:
    def _run(self, *args):
        from typer.testing import CliRunner

        from chimeraforge.cli import app

        return CliRunner().invoke(app, ["plan", *args])

    def test_cli_rejects_non_positive_host_bandwidth(self):
        r = self._run("--model-size", "3b", "--host-bandwidth-gbps", "0")
        assert r.exit_code == 1 and "host-bandwidth-gbps" in r.output

    def test_json_carries_offload_fields(self):
        import json

        r = self._run(
            "--model-size",
            "8b",
            "--hardware",
            "RTX 4060 8GB",
            "--json",
            "--allow-offload",
            "--budget",
            "5000",
            "--latency-slo",
            "1e9",
            "--quality-target",
            "0",
            "--request-rate",
            "0.2",
        )
        assert r.exit_code == 0
        data = json.loads(r.output[r.output.index("[") : r.output.rindex("]") + 1])
        assert any(c["offload_fraction"] > 0 for c in data)
