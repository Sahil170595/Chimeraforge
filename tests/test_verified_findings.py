"""Regressions for the blind-review claims I verified myself before acting.

Each was reported by a review agent, reproduced here on the main thread, and
only then fixed. The ones that did not reproduce are noted in the report rather
than defended with a test.
"""

from __future__ import annotations

import json
import pathlib

import pytest

from chimeraforge.planner.constants import DEFAULT_HOST_LINK_GBPS
from chimeraforge.planner.formatter import _finite
from chimeraforge.planner.hardware import GPU_DB
from chimeraforge.planner.service import run_plan


class TestCpuOffloadUsesTheHostLink:
    """`GPUSpec.interconnect_gbps` is the tensor-parallel GPU-to-GPU fabric.
    Using an H100's 900 GB/s NVLink as its path to system DRAM overstated
    offloaded decode by more than an order of magnitude -- on exactly the configs
    where offload is the only way to fit."""

    def test_the_default_is_a_pcie_figure(self):
        assert DEFAULT_HOST_LINK_GBPS == pytest.approx(32.0)

    @pytest.mark.parametrize("gpu", ["H100 80GB", "A100 80GB", "B200 180GB"])
    def test_no_nvlink_figure_is_within_reach_of_it(self, gpu):
        assert GPU_DB[gpu].interconnect_gbps > DEFAULT_HOST_LINK_GBPS * 10

    def test_offloaded_decode_is_bounded_by_the_host_link(self):
        r = run_plan(
            model_size="8b",
            hardware="RTX 4060 8GB",
            allow_offload=True,
            request_rate=0.2,
            budget=1e9,
            quality_target=0.0,
            latency_slo=1e9,
            context_length=2048,
        )
        off = [c for c in r.candidates if c.offload_fraction > 0]
        assert off, "expected an offloaded candidate"
        for c in off:
            assert c.host_bandwidth_gbps == DEFAULT_HOST_LINK_GBPS


class TestKvQuantIsCaseInsensitiveEndToEnd:
    """Validation lowercased for its membership test and then forwarded the raw
    string, so `Q4` passed the check and then missed KV_QUANT_BYTES -- silently
    returning the FP16 plan, with a different VRAM figure and no warning."""

    def _plan(self, kv):
        return run_plan(
            model_size="8b",
            hardware="RTX 4090 24GB",
            kv_quant=kv,
            budget=1e9,
            quality_target=0.0,
            latency_slo=1e9,
            context_length=8192,
        ).candidates[0]

    @pytest.mark.parametrize("pair", [("q4", "Q4"), ("q8", "Q8"), ("fp16", "FP16")])
    def test_case_does_not_change_the_answer(self, pair):
        lo, up = (self._plan(p) for p in pair)
        assert lo.vram_gb == pytest.approx(up.vram_gb)
        assert lo.quant == up.quant

    def test_a_quantized_kv_cache_is_smaller_and_says_so(self):
        for cased in ("Q4", "q4"):
            c = self._plan(cased)
            assert c.vram_gb < self._plan("fp16").vram_gb
            assert any("KV cache quantized" in w for w in c.warnings)


class TestJsonIsRfc8259:
    """`json.dumps` emits the bare token `Infinity`, a CPython extension. Python
    clients tolerate it; JSON.parse in a JS/TS MCP host throws and loses the whole
    tool result, not just the field."""

    def test_non_finite_becomes_null(self):
        assert _finite(float("inf")) is None
        assert _finite(float("-inf")) is None
        assert _finite(float("nan")) is None
        assert _finite(1.5) == 1.5

    def test_it_recurses(self):
        got = _finite({"a": float("inf"), "b": [1.0, float("nan")], "c": {"d": float("-inf")}})
        assert got == {"a": None, "b": [1.0, None], "c": {"d": None}}

    def test_plan_json_parses_strictly(self):
        from typer.testing import CliRunner

        from chimeraforge.cli import app

        r = CliRunner().invoke(
            app,
            [
                "plan",
                "--model-size",
                "8b",
                "--hardware",
                "RTX 4080 12GB",
                "--budget",
                "1e9",
                "--quality-target",
                "0",
                "--json",
            ],
        )
        assert r.exit_code == 0
        raw = r.output[r.output.index("[") : r.output.rindex("]") + 1]
        assert "Infinity" not in raw and "NaN" not in raw

        def reject(const):
            raise AssertionError(f"non-JSON constant on the wire: {const}")

        json.loads(raw, parse_constant=reject)


class TestRefitAccumulatesOntoMeasurements:
    """`refit` based on the bundled snapshot while WRITING to the measured corpus,
    so it silently deleted every row `measure` had accumulated -- throughput rows
    and serial fractions both -- with no warning, no backup and exit 0."""

    def test_a_measured_row_survives_a_refit(self, tmp_path, monkeypatch):
        from typer.testing import CliRunner

        from chimeraforge.cli import app

        monkeypatch.setenv("CHIMERAFORGE_CACHE", str(tmp_path))
        from chimeraforge.planner.resolver import measured_corpus_path

        cp = pathlib.Path(measured_corpus_path())
        cp.parent.mkdir(parents=True, exist_ok=True)
        bundled = pathlib.Path("src/chimeraforge/planner/data/fitted_models.json")
        corpus = json.loads(bundled.read_text(encoding="utf-8"))
        corpus["throughput"]["lookup"]["mymodel|ollama|FP16"] = 42.0
        corpus["scaling"]["serial_fractions"]["mymodel|ollama"] = 0.5
        cp.write_text(json.dumps(corpus), encoding="utf-8")

        bench = {
            "model": "other",
            "backend": "ollama",
            "quant": "FP16",
            "aggregate": {
                "throughput_tps": {"mean": 11.0, "n": 3},
                "total_duration_ms": {"mean": 100.0, "n": 3},
            },
            "n_runs": 3,
        }
        bf = tmp_path / "bench.json"
        bf.write_text(json.dumps(bench), encoding="utf-8")

        r = CliRunner().invoke(app, ["refit", "--bench-files", str(bf)])
        assert r.exit_code == 0, r.output

        after = json.loads(cp.read_text(encoding="utf-8"))
        assert after["throughput"]["lookup"].get("mymodel|ollama|FP16") == 42.0
        assert after["scaling"]["serial_fractions"].get("mymodel|ollama") == 0.5
        assert "other|ollama|FP16" in after["throughput"]["lookup"], "the new row must land too"
