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


from helpers import make_result as _make_result_base
from helpers import write_bench_json as _write_bench_json


def _make_result(**kwargs: object) -> dict:
    """Build a bench result dict with populated individual_runs (needed for CV tests)."""
    throughput_mean = kwargs.get("throughput_mean", 95.0)
    ttft_mean = kwargs.get("ttft_mean", 50.0)
    runs = kwargs.get("runs", 5)
    result = _make_result_base(**kwargs)
    result["individual_runs"] = [
        {"throughput_tps": throughput_mean + i * 0.1, "ttft_ms": ttft_mean} for i in range(runs)
    ]
    return result


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
        _write_bench_json(
            f,
            [
                _make_result(
                    model="llama3.2-3b", backend="ollama", quant=None, throughput_mean=100.0
                ),
                _make_result(
                    model="llama3.2-3b", backend="ollama", quant="Q4_K_M", throughput_mean=190.0
                ),
            ],
        )
        merged, summary = refit_from_bench([f])
        assert summary["bench_results_loaded"] == 2
        assert summary["throughput_entries_updated"] == 2
        assert "llama3.2-3b|ollama|FP16" in merged["throughput"]["lookup"]

    def test_summary_counts(self, tmp_path: Path):
        from chimeraforge.refit.fitter import refit_from_bench

        f = tmp_path / "bench.json"
        _write_bench_json(
            f,
            [
                _make_result(model="a", backend="b", duration_mean=800.0),
            ],
        )
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

    def test_refit_validate_flag(self, tmp_path: Path):
        from typer.testing import CliRunner

        from chimeraforge.cli import app

        f = tmp_path / "bench.json"
        _write_bench_json(f, [_make_result()])
        out = tmp_path / "fitted.json"

        runner = CliRunner()
        result = runner.invoke(
            app,
            [
                "refit",
                "--bench-files",
                str(f),
                "--output",
                str(out),
                "--validate",
            ],
        )
        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# TestBayesianBlending
# ---------------------------------------------------------------------------


class TestBayesianBlending:
    def test_full_confidence(self):
        from chimeraforge.refit.fitter import bayesian_blend_throughput

        existing = {"a|b|FP16": 100.0}
        measured = {"a|b|FP16": 200.0}
        blended = bayesian_blend_throughput(existing, measured, n_total_runs=100)
        # w = min(1.0, 100/50) = 1.0, so fully measured
        assert blended["a|b|FP16"] == pytest.approx(200.0)

    def test_partial_confidence(self):
        from chimeraforge.refit.fitter import bayesian_blend_throughput

        existing = {"a|b|FP16": 100.0}
        measured = {"a|b|FP16": 200.0}
        blended = bayesian_blend_throughput(existing, measured, n_total_runs=25)
        # w = 25/50 = 0.5 -> 0.5*100 + 0.5*200 = 150
        assert blended["a|b|FP16"] == pytest.approx(150.0)

    def test_new_entry_no_prior(self):
        from chimeraforge.refit.fitter import bayesian_blend_throughput

        existing = {"a|b|FP16": 100.0}
        measured = {"new|b|FP16": 50.0}
        blended = bayesian_blend_throughput(existing, measured, n_total_runs=10)
        # New key -> no blending, just measured
        assert blended["new|b|FP16"] == 50.0
        # Existing preserved
        assert blended["a|b|FP16"] == 100.0

    def test_zero_runs(self):
        from chimeraforge.refit.fitter import bayesian_blend_throughput

        existing = {"a|b|FP16": 100.0}
        measured = {"a|b|FP16": 200.0}
        blended = bayesian_blend_throughput(existing, measured, n_total_runs=0)
        # w = 0 -> fully existing
        assert blended["a|b|FP16"] == pytest.approx(100.0)


# ---------------------------------------------------------------------------
# TestHardwareOffsets
# ---------------------------------------------------------------------------


class TestHardwareOffsets:
    def test_compute_offsets(self):
        from chimeraforge.refit.fitter import compute_hardware_offsets

        existing = {
            "throughput": {
                "lookup": {"m|b|FP16": 50.0},
            },
        }
        results = [_make_result(model="m", backend="b", quant=None, throughput_mean=75.0)]
        offsets = compute_hardware_offsets(results, existing)
        # 75/50 = 1.5
        assert offsets["m|b"] == pytest.approx(1.5)

    def test_no_predicted_entries(self):
        from chimeraforge.refit.fitter import compute_hardware_offsets

        existing = {"throughput": {"lookup": {}}}
        results = [_make_result()]
        offsets = compute_hardware_offsets(results, existing)
        assert offsets == {}


# ---------------------------------------------------------------------------
# TestCountTotalRuns
# ---------------------------------------------------------------------------


class TestCountTotalRuns:
    def test_from_runs_field(self):
        from chimeraforge.refit.fitter import count_total_runs

        results = [{"runs": 5}, {"runs": 3}]
        assert count_total_runs(results) == 8

    def test_from_individual_runs(self):
        from chimeraforge.refit.fitter import count_total_runs

        results = [{"individual_runs": [1, 2, 3]}]
        assert count_total_runs(results) == 3


# ---------------------------------------------------------------------------
# TestValidator
# ---------------------------------------------------------------------------


class TestValidator:
    def _valid_fitted(self) -> dict:
        return {
            "throughput": {
                "lookup": {"m|b|FP16": 95.0},
                "quant_multipliers": {
                    "FP16": 1.0,
                    "Q8_0": 1.1,
                    "Q6_K": 1.3,
                    "Q5_K_M": 1.5,
                    "Q4_K_M": 1.7,
                    "Q3_K_S": 2.0,
                    "Q2_K": 2.3,
                },
                "size_power_a": 100.0,
                "size_power_b": 0.5,
            },
            "latency": {
                "service_times": {"m|b": 500.0},
                "safety_factor": 0.7,
            },
            "vram": {
                "overhead_factor": 1.1,
            },
        }

    def test_valid_passes(self):
        from chimeraforge.refit.validator import validate_fitted_models

        result = validate_fitted_models(self._valid_fitted())
        assert result.passed
        assert result.n_failed == 0

    def test_negative_throughput_fails(self):
        from chimeraforge.refit.validator import validate_fitted_models

        fitted = self._valid_fitted()
        fitted["throughput"]["lookup"]["bad|b|FP16"] = -1.0
        result = validate_fitted_models(fitted)
        failed_names = [c.name for c in result.checks if not c.passed]
        assert "throughput_positive" in failed_names

    def test_fp16_not_one_fails(self):
        from chimeraforge.refit.validator import validate_fitted_models

        fitted = self._valid_fitted()
        fitted["throughput"]["quant_multipliers"]["FP16"] = 0.5
        result = validate_fitted_models(fitted)
        failed_names = [c.name for c in result.checks if not c.passed]
        assert "quant_fp16_is_one" in failed_names

    def test_format_validation_json(self):
        import json

        from chimeraforge.refit.validator import format_validation_json, validate_fitted_models

        result = validate_fitted_models(self._valid_fitted())
        j = format_validation_json(result)
        parsed = json.loads(j)
        assert parsed["passed"] is True
        assert len(parsed["checks"]) == 10

    def test_format_validation_table(self, tmp_path: Path):
        from rich.console import Console

        from chimeraforge.refit.validator import format_validation_table, validate_fitted_models

        result = validate_fitted_models(self._valid_fitted())
        c = Console(file=open(tmp_path / "out.txt", "w"), force_terminal=False)
        format_validation_table(result, c)
