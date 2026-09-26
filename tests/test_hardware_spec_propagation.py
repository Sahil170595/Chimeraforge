"""The resolved GPU spec must reach the models that predict from it.

0.34.0 shipped `--gpu-*` overrides and unlisted-card planning. The engine
resolved the spec correctly, then passed only its NAME onward, and every model
re-looked it up with `get_gpu(name)`. For an unlisted card that lookup found
nothing and fell back to the reference rig: an "RTX 6090" at 1300 or 2600 GB/s
both reported 146.3 tok/s -- the reference laptop's own row -- labelled
`measured`, with TTFT 0.0 despite a supplied FP16 figure. For a listed card, a
bandwidth override was warned about as in force and silently ignored.

These pin the property the roadmap stated for P8.6 and nothing tested: overrides
given a known card's published figures reproduce that card's plan exactly, and
different figures give a different plan.
"""

from __future__ import annotations

import pytest

from chimeraforge.planner.hardware import GPU_DB
from chimeraforge.planner.provenance import PROV_MEASURED, prov_class
from chimeraforge.planner.service import run_plan

KW = dict(
    models=["llama3.2-1b"],
    quality_target=0.0,
    budget=1e9,
    latency_slo=1e9,
    allow_network=False,
)


def _fp16_ollama(plan):
    return next(c for c in plan.candidates if c.backend == "ollama" and c.quant == "FP16")


def _published(name: str) -> dict:
    g = GPU_DB[name]
    return {
        "vram_gb": g.vram_gb,
        "bandwidth_gbps": g.bandwidth_gbps,
        "fp16_tflops": g.fp16_tflops,
        "tdp_watts": g.tdp_watts,
        "interconnect_gbps": g.interconnect_gbps,
        "cost_per_hour": g.cost_per_hour,
    }


class TestUnlistedCard:
    def _plan(self, bw, tflops=200.0):
        return run_plan(
            hardware="RTX 6090 48GB",
            gpu_overrides={
                "vram_gb": 48,
                "bandwidth_gbps": bw,
                "fp16_tflops": tflops,
                "cost_per_hour": 0.05,
            },
            **KW,
        )

    def test_throughput_follows_the_supplied_bandwidth(self):
        slow, fast = _fp16_ollama(self._plan(1300)), _fp16_ollama(self._plan(2600))
        assert fast.throughput_tps > slow.throughput_tps * 1.5

    def test_it_is_never_labelled_a_measurement(self):
        """The corpus measured the reference laptop, not a card the user described."""
        c = _fp16_ollama(self._plan(1300))
        assert prov_class(c.provenance["throughput"]) != PROV_MEASURED

    def test_a_supplied_fp16_figure_gives_a_real_ttft(self):
        assert _fp16_ollama(self._plan(1300)).ttft_ms > 0


class TestOverridesOnAListedCard:
    def test_a_bandwidth_override_moves_throughput(self):
        base = _fp16_ollama(run_plan(hardware="RTX 4090 24GB", **KW))
        halved = _fp16_ollama(
            run_plan(hardware="RTX 4090 24GB", gpu_overrides={"bandwidth_gbps": 504.0}, **KW)
        )
        assert halved.throughput_tps == pytest.approx(base.throughput_tps / 2, rel=0.02)

    def test_overriding_the_reference_card_stops_it_being_a_measurement(self):
        c = _fp16_ollama(
            run_plan(hardware="RTX 4080 12GB", gpu_overrides={"bandwidth_gbps": 864.0}, **KW)
        )
        assert prov_class(c.provenance["throughput"]) != PROV_MEASURED

    def test_the_untouched_reference_card_is_still_a_measurement(self):
        c = _fp16_ollama(run_plan(hardware="RTX 4080 12GB", **KW))
        assert prov_class(c.provenance["throughput"]) == PROV_MEASURED


class TestPublishedFiguresReproduceTheCard:
    @pytest.mark.parametrize("name", ["RTX 4090 24GB", "H100 80GB", "RTX 3090 24GB"])
    def test_same_figures_same_plan(self, name):
        known = _fp16_ollama(run_plan(hardware=name, **KW))
        described = _fp16_ollama(
            run_plan(hardware=f"my {name} twin", gpu_overrides=_published(name), **KW)
        )
        assert described.throughput_tps == pytest.approx(known.throughput_tps)
        assert described.ttft_ms == pytest.approx(known.ttft_ms)
        assert described.vram_gb == pytest.approx(known.vram_gb)
        assert described.monthly_cost == pytest.approx(known.monthly_cost)
