"""ChimeraForge Refit — unit tests.

Tests the refit pipeline: loading bench results, extracting throughput
lookups / quant multipliers / service times, fitting power law,
merging into existing fitted_models, and CLI integration.

Run:
    pytest tests/test_refit.py -v
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Helpers — synthetic bench result dicts
# ---------------------------------------------------------------------------


def _make_result(
    model: str = "llama3.2-3b",
    backend: str = "ollama",
    quant: str | None = None,
    throughput_mean: float = 95.0,
    ttft_mean: float = 50.0,
    duration_mean: float = 1000.0,
    runs: int = 5,
    workload: str = "single",
    context_length: int = 2048,
) -> dict:
    """Build a minimal bench result dict matching the BenchmarkResult schema."""
    individual = [
        {"throughput_tps": throughput_mean + i * 0.1, "ttft_ms": ttft_mean}
        for i in range(runs)
    ]
    return {
        "model": model,
        "backend": backend,
        "quant": quant,
        "workload": workload,
        "context_length": context_length,
        "runs": runs,
        "aggregate": {
            "count": runs,
            "throughput_tps": {"mean": throughput_mean, "p50": throughput_mean, "p95": throughput_mean, "p99": throughput_mean, "min": throughput_mean, "max": throughput_mean, "stddev": 0.5},
            "ttft_ms": {"mean": ttft_mean, "p50": ttft_mean, "p95": ttft_mean, "p99": ttft_mean, "min": ttft_mean, "max": ttft_mean, "stddev": 1.0},
            "total_duration_ms": {"mean": duration_mean, "p50": duration_mean, "p95": duration_mean, "p99": duration_mean, "min": duration_mean, "max": duration_mean, "stddev": 10.0},
            "tokens_generated": 640,
        },
        "individual_runs": individual,
        "environment": {},
        "timestamp": "2026-01-01T00:00:00+00:00",
        "warnings": [],
    }


def _write_bench_json(path: Path, results: list[dict]) -> None:
    path.write_text(json.dumps(results, indent=2))


# ---------------------------------------------------------------------------
# TestLoadBenchResults
# ---------------------------------------------------------------------------


class TestLoadBenchResults:
    def test_load_single_file(self, tmp_path: Path):
        from chimeraforge.refit.fitter import load_bench_results

        f = tmp_path / "run1.json"
        _write_bench_json(f, [_make_result()])
        results = load_bench_results([f])
        assert len(results) == 1
        assert results[0]["model"] == "llama3.2-3b"

    def test_load_multiple_files(self, tmp_path: Path):
        from chimeraforge.refit.fitter import load_bench_results

        f1 = tmp_path / "run1.json"
        f2 = tmp_path / "run2.json"
        _write_bench_json(f1, [_make_result(model="a")])
        _write_bench_json(f2, [_make_result(model="b"), _make_result(model="c")])
        results = load_bench_results([f1, f2])
        assert len(results) == 3

    def test_missing_file_raises(self, tmp_path: Path):
        from chimeraforge.refit.fitter import load_bench_results

        with pytest.raises(FileNotFoundError):
            load_bench_results([tmp_path / "nope.json"])


# ---------------------------------------------------------------------------
# TestExtractThroughput
# ---------------------------------------------------------------------------


class TestExtractThroughput:
    def test_single_result(self):
        from chimeraforge.refit.fitter import extract_throughput_lookup

        results = [_make_result(model="m", backend="b", quant="Q4_K_M", throughput_mean=42.0)]
        lookup = extract_throughput_lookup(results)
        assert lookup == {"m|b|Q4_K_M": 42.0}

    def test_multiple_quants(self):
        from chimeraforge.refit.fitter import extract_throughput_lookup

        results = [
            _make_result(model="m", backend="b", quant="Q4_K_M", throughput_mean=40.0),
            _make_result(model="m", backend="b", quant="Q8_0", throughput_mean=30.0),
        ]
        lookup = extract_throughput_lookup(results)
        assert len(lookup) == 2
        assert lookup["m|b|Q4_K_M"] == 40.0
        assert lookup["m|b|Q8_0"] == 30.0

    def test_none_quant_uses_fp16(self):
        from chimeraforge.refit.fitter import extract_throughput_lookup

        results = [_make_result(quant=None, throughput_mean=100.0)]
        lookup = extract_throughput_lookup(results)
        assert "llama3.2-3b|ollama|FP16" in lookup

    def test_empty_results(self):
        from chimeraforge.refit.fitter import extract_throughput_lookup

        assert extract_throughput_lookup([]) == {}


# ---------------------------------------------------------------------------
# TestExtractQuantMultipliers
# ---------------------------------------------------------------------------


class TestExtractQuantMultipliers:
    def test_paired_fp16_and_quant(self):
        from chimeraforge.refit.fitter import extract_quant_multipliers

        results = [
            _make_result(model="m", backend="b", quant=None, throughput_mean=100.0),
            _make_result(model="m", backend="b", quant="Q4_K_M", throughput_mean=190.0),
        ]
        qm = extract_quant_multipliers(results, {"FP16": 1.0})
        assert qm["FP16"] == 1.0
        assert qm["Q4_K_M"] == pytest.approx(1.9)

    def test_no_fp16_reference_falls_back(self):
        from chimeraforge.refit.fitter import extract_quant_multipliers

        results = [
            _make_result(model="m", backend="b", quant="Q4_K_M", throughput_mean=190.0),
        ]
        existing = {"FP16": 1.0, "Q4_K_M": 1.9, "Q8_0": 1.3}
        qm = extract_quant_multipliers(results, existing)
        # No FP16 baseline -> Q4_K_M falls back to existing
        assert qm["Q4_K_M"] == 1.9
        assert qm["Q8_0"] == 1.3

    def test_multiple_models_averaged(self):
        from chimeraforge.refit.fitter import extract_quant_multipliers

        results = [
            _make_result(model="a", backend="b", quant=None, throughput_mean=100.0),
            _make_result(model="a", backend="b", quant="Q4_K_M", throughput_mean=200.0),
            _make_result(model="c", backend="b", quant=None, throughput_mean=50.0),
            _make_result(model="c", backend="b", quant="Q4_K_M", throughput_mean=90.0),
        ]
        qm = extract_quant_multipliers(results, {"FP16": 1.0})
        # a: 200/100=2.0, c: 90/50=1.8, avg=1.9
        assert qm["Q4_K_M"] == pytest.approx(1.9)


# ---------------------------------------------------------------------------
# TestExtractServiceTimes
# ---------------------------------------------------------------------------


class TestExtractServiceTimes:
    def test_single_result(self):
        from chimeraforge.refit.fitter import extract_service_times

        results = [_make_result(model="m", backend="b", duration_mean=500.0)]
        st = extract_service_times(results)
        assert st == {"m|b": 500.0}

    def test_multiple_quants_averaged(self):
        from chimeraforge.refit.fitter import extract_service_times

        results = [
            _make_result(model="m", backend="b", quant="Q4_K_M", duration_mean=400.0),
            _make_result(model="m", backend="b", quant="Q8_0", duration_mean=600.0),
        ]
        st = extract_service_times(results)
        assert st["m|b"] == pytest.approx(500.0)


# ---------------------------------------------------------------------------
# TestFitPowerLaw
# ---------------------------------------------------------------------------


class TestFitPowerLaw:
    def test_sufficient_data_returns_fitted(self):
        from chimeraforge.refit.fitter import fit_power_law

        # 3 FP16 entries with known model params
        throughputs = {
            "llama3.2-1b|ollama|FP16": 146.0,
            "qwen2.5-1.5b|ollama|FP16": 139.0,
            "llama3.2-3b|ollama|FP16": 95.0,
        }
        a, b = fit_power_law(throughputs)
        # Should return something other than defaults if scipy is available
        # If scipy is not installed, defaults are returned
        assert a > 0
        assert b > 0

    def test_insufficient_data_returns_defaults(self):
        from chimeraforge.refit.fitter import fit_power_law

        throughputs = {
            "llama3.2-1b|ollama|FP16": 146.0,
        }
        a, b = fit_power_law(throughputs)
        assert (a, b) == (100.0, 0.5)

    def test_scipy_unavailable_returns_defaults(self, monkeypatch):
        from chimeraforge.refit import fitter

        # Simulate scipy import failure
        import builtins

        real_import = builtins.__import__

        def _mock_import(name, *args, **kwargs):
            if name == "scipy.optimize" or name.startswith("scipy"):
                raise ImportError("no scipy")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", _mock_import)

        throughputs = {
            "llama3.2-1b|ollama|FP16": 146.0,
            "qwen2.5-1.5b|ollama|FP16": 139.0,
            "llama3.2-3b|ollama|FP16": 95.0,
        }
        a, b = fitter.fit_power_law(throughputs)
        assert (a, b) == (100.0, 0.5)


# ---------------------------------------------------------------------------
# TestMergeFittedModels
# ---------------------------------------------------------------------------


class TestMergeFittedModels:
    def _base(self) -> dict:
        return {
            "throughput": {
                "lookup": {"old|b|FP16": 10.0},
                "quant_multipliers": {"FP16": 1.0, "Q8_0": 1.3},
                "size_power_a": 100.0,
                "size_power_b": 0.5,
                "fitted": False,
            },
            "latency": {
                "service_times": {"old|b": 999.0},
                "safety_factor": 0.7,
                "fitted": False,
            },
        }

    def test_new_throughput_added_existing_preserved(self):
        from chimeraforge.refit.fitter import merge_fitted_models

        merged = merge_fitted_models(
            self._base(),
            throughput_lookup={"new|b|FP16": 50.0},
            quant_multipliers={"FP16": 1.0, "Q8_0": 1.3},
            service_times={},
            power_law=None,
        )
        tp = merged["throughput"]["lookup"]
        assert tp["old|b|FP16"] == 10.0
        assert tp["new|b|FP16"] == 50.0

    def test_service_times_merged(self):
        from chimeraforge.refit.fitter import merge_fitted_models

        merged = merge_fitted_models(
            self._base(),
            throughput_lookup={},
            quant_multipliers={"FP16": 1.0},
            service_times={"new|b": 500.0},
            power_law=None,
        )
        st = merged["latency"]["service_times"]
        assert st["old|b"] == 999.0
        assert st["new|b"] == 500.0

    def test_quant_multipliers_updated(self):
        from chimeraforge.refit.fitter import merge_fitted_models

        merged = merge_fitted_models(
            self._base(),
            throughput_lookup={},
            quant_multipliers={"FP16": 1.0, "Q8_0": 1.5, "Q4_K_M": 2.0},
            service_times={},
            power_law=None,
        )
        qm = merged["throughput"]["quant_multipliers"]
        assert qm["Q8_0"] == 1.5
        assert qm["Q4_K_M"] == 2.0

    def test_power_law_updated(self):
        from chimeraforge.refit.fitter import merge_fitted_models

        merged = merge_fitted_models(
            self._base(),
            throughput_lookup={},
            quant_multipliers={"FP16": 1.0},
            service_times={},
            power_law=(80.0, 0.3),
        )
        assert merged["throughput"]["size_power_a"] == 80.0
        assert merged["throughput"]["size_power_b"] == 0.3


# ---------------------------------------------------------------------------
# TestRefitFromBench
# ---------------------------------------------------------------------------


class TestRefitFromBench:
    def test_end_to_end(self, tmp_path: Path):
        from chimeraforge.refit.fitter import refit_from_bench

        f = tmp_path / "bench.json"
        _write_bench_json(f, [
            _make_result(model="llama3.2-3b", backend="ollama", quant=None, throughput_mean=100.0),
            _make_result(model="llama3.2-3b", backend="ollama", quant="Q4_K_M", throughput_mean=190.0),
        ])
        merged, summary = refit_from_bench([f])
        assert summary["bench_results_loaded"] == 2
        assert summary["throughput_entries_updated"] == 2
        assert "llama3.2-3b|ollama|FP16" in merged["throughput"]["lookup"]

    def test_summary_counts(self, tmp_path: Path):
        from chimeraforge.refit.fitter import refit_from_bench

        f = tmp_path / "bench.json"
        _write_bench_json(f, [
            _make_result(model="a", backend="b", duration_mean=800.0),
        ])
        _, summary = refit_from_bench([f])
        assert summary["service_times_updated"] == 1

    def test_uses_bundled_base(self, tmp_path: Path):
        from chimeraforge.refit.fitter import refit_from_bench

        f = tmp_path / "bench.json"
        _write_bench_json(f, [_make_result()])
        merged, _ = refit_from_bench([f])
        # Should have entries from bundled fitted_models.json
        assert "vram" in merged
        assert "quality" in merged


# ---------------------------------------------------------------------------
# TestSaveFittedModels
# ---------------------------------------------------------------------------


class TestSaveFittedModels:
    def test_round_trip(self, tmp_path: Path):
        from chimeraforge.refit.fitter import save_fitted_models

        data = {"throughput": {"lookup": {"a|b|FP16": 42.0}}}
        out = tmp_path / "sub" / "fitted.json"
        saved = save_fitted_models(data, out)
        assert saved.exists()
        loaded = json.loads(saved.read_text())
        assert loaded == data


# ---------------------------------------------------------------------------
# TestCLIRefit
# ---------------------------------------------------------------------------


class TestCLIRefit:
    @staticmethod
    def _strip_ansi(text: str) -> str:
        import re

        return re.sub(r"\x1b\[[0-9;]*m", "", text)

    def test_refit_help(self):
        from typer.testing import CliRunner

        from chimeraforge.cli import app

        runner = CliRunner()
        result = runner.invoke(app, ["refit", "--help"])
        output = self._strip_ansi(result.output)
        assert result.exit_code == 0
        assert "--bench-dir" in output

    def test_refit_no_input_exits_1(self):
        from typer.testing import CliRunner

        from chimeraforge.cli import app

        runner = CliRunner()
        result = runner.invoke(app, ["refit"])
        assert result.exit_code == 1

    def test_refit_with_bench_file(self, tmp_path: Path):
        from typer.testing import CliRunner

        from chimeraforge.cli import app

        f = tmp_path / "bench.json"
        _write_bench_json(f, [_make_result()])
        out = tmp_path / "fitted.json"

        runner = CliRunner()
        result = runner.invoke(app, ["refit", "--bench-files", str(f), "--output", str(out)])
        assert result.exit_code == 0
        assert out.exists()
