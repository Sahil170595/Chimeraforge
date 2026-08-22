"""Tests for the write path into the measured corpus.

Batch C of an adversarial review. The corpus is what makes a number `measured`,
and every stage of the path that fills it was broken in a different way:

- `bench --all-quants` produced rows that differ only by noise, each labelled a
  different quantization, because the label never reaches the backend;
- `fit_power_law` returned a placeholder when it could not fit, and the merge
  wrote it, replacing the TR133 coefficients;
- `refit` wrote the result to a directory nothing reads;
- `measure` benchmarked a scaling factor the planner does not consume and
  printed it in green as `(measured)`.

The failure mode they share is that each stage reports success. Nothing crashes,
nothing warns, and the corrupted value comes back later wearing the strongest
provenance label the tool has.
"""

from __future__ import annotations

import pytest

from chimeraforge.refit.fitter import fit_power_law, merge_fitted_models


class TestPowerLawNeverOverwritesWithAPlaceholder:
    """`merge_fitted_models` writes the fit when it `is not None`, and a tuple is
    not None -- so returning a placeholder pair silently replaced the TR133
    coefficients with a=100/b=0.5."""

    def test_under_determined_returns_none(self):
        assert fit_power_law({"llama3.2-1b|ollama|FP16": 146.0}) is None

    def test_no_fp16_rows_returns_none(self):
        # The fit only consumes FP16 points; a corpus of quantized rows alone is
        # under-determined however many rows it has.
        rows = {f"m{i}|ollama|Q4_K_M": 100.0 + i for i in range(10)}
        assert fit_power_law(rows) is None

    def test_enough_points_still_fits(self):
        pytest.importorskip("scipy", reason="curve fitting needs the refit extra")
        fitted = fit_power_law(
            {
                "llama3.2-1b|ollama|FP16": 146.0,
                "qwen2.5-1.5b|ollama|FP16": 139.0,
                "llama3.2-3b|ollama|FP16": 95.0,
            }
        )
        assert fitted is not None
        a, b = fitted
        assert a > 0 and b > 0

    def test_none_leaves_existing_coefficients_untouched(self):
        existing = {"throughput": {"size_power_a": 72.11, "size_power_b": 0.0888}}
        merged = merge_fitted_models(
            existing,
            throughput_lookup={},
            quant_multipliers={},
            service_times={},
            power_law=None,
        )
        assert merged["throughput"]["size_power_a"] == 72.11
        assert merged["throughput"]["size_power_b"] == 0.0888

    def test_a_real_fit_does_overwrite(self):
        merged = merge_fitted_models(
            {"throughput": {"size_power_a": 72.11, "size_power_b": 0.0888}},
            throughput_lookup={},
            quant_multipliers={},
            service_times={},
            power_law=(50.0, 0.2),
        )
        assert merged["throughput"]["size_power_a"] == 50.0

    def test_the_summary_flag_tracks_the_fit_not_a_magic_pair(self):
        """`power_law_refit` was computed as `pl != (100.0, 0.5)`, so the code
        already knew the placeholder meant 'no fit' while writing it anyway."""
        import inspect

        from chimeraforge.refit import fitter

        src = inspect.getsource(fitter)
        assert '"power_law_refit": pl is not None' in src
        assert "pl != (100.0, 0.5)" not in src

    def test_the_corruption_would_have_been_severe(self):
        """Documents the magnitude, so nobody restores the placeholder as
        'harmless defaults'."""
        real_a, real_b = 72.11010249423731, 0.08877472521007239
        for params, tolerance in ((70.0, -0.70), (0.5, 0.70)):
            real = real_a * params**-real_b
            placeholder = 100.0 * params**-0.5
            drift = placeholder / real - 1
            assert abs(drift) > abs(tolerance), (
                f"at {params}B the placeholder drifts {drift:+.0%} from the fit"
            )


class TestRefitWritesWherePlanReads:
    def test_default_output_is_the_path_the_planner_loads(self):
        """refit defaulted to platformdirs' user_data_dir while plan/suggest/MCP
        read ~/.cache/chimeraforge, so a successful refit printed 'Saved to ...',
        exited 0, and was completely inert."""
        import inspect

        from chimeraforge.commands import refit as refit_cmd

        src = inspect.getsource(refit_cmd)
        assert "measured_corpus_path" in src
        # The import, not any mention -- the comment explaining the fix names the
        # old path, and a substring check would match its own documentation.
        assert "from platformdirs import user_data_dir" not in src

    def test_that_path_honours_the_cache_override(self, tmp_path, monkeypatch):
        from chimeraforge.planner.resolver import measured_corpus_path

        monkeypatch.setenv("CHIMERAFORGE_CACHE", str(tmp_path))
        assert str(tmp_path) in str(measured_corpus_path())

    def test_read_and_write_sides_agree(self, tmp_path, monkeypatch):
        """The property, not the implementation: whatever refit defaults to must be
        the file load_effective_models opens."""
        import json

        from chimeraforge.planner.models import load_effective_models
        from chimeraforge.planner.resolver import measured_corpus_path

        monkeypatch.setenv("CHIMERAFORGE_CACHE", str(tmp_path))
        target = measured_corpus_path()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps({"throughput": {"lookup": {"sentinel|ollama|FP16": 1234.0}}}),
            encoding="utf-8",
        )
        models = load_effective_models()
        assert models.throughput.lookup.get("sentinel|ollama|FP16") == 1234.0


class TestQuantSweepDisclosesThatItAppliedNothing:
    """`quant` reaches the result object but never the backend -- no adapter takes
    a per-request quantization, because a quant is a property of the loaded
    artifact. Every row of a sweep is the same served model re-run."""

    def test_every_swept_row_carries_the_warning(self):
        import asyncio
        from unittest.mock import patch

        from chimeraforge.bench.runner import run_quant_sweep

        async def fake_run_benchmark(model, backend_name, quant, **kwargs):
            from chimeraforge.bench.metrics import BenchmarkResult

            result = BenchmarkResult.__new__(BenchmarkResult)
            object.__setattr__(result, "warnings", [])
            object.__setattr__(result, "quant", quant)
            return result

        with patch("chimeraforge.bench.runner.run_benchmark", fake_run_benchmark):
            results = asyncio.run(run_quant_sweep("m", "ollama", quants=["Q4_K_M", "Q2_K", "FP16"]))
        assert len(results) == 3
        for r in results:
            hits = [w for w in r.warnings if "NOT applied" in w]
            assert hits, f"{r.quant} row does not disclose that the quant was not applied"
            assert r.quant in hits[0]

    def test_the_warning_matches_the_context_sweep_precedent(self):
        """The context sweep already warns for the same reason; the wording should
        be recognisably the same class of disclosure."""
        import inspect

        from chimeraforge.bench import runner

        src = inspect.getsource(runner.run_quant_sweep)
        assert "NOT applied" in src
        assert "per-request quantization" in src


class TestScalingIsNotPresentedAsInformingThePlan:
    def test_measure_does_not_call_eta_measured_in_green(self):
        """eta is hardcoded to 1.0 in the engine and ScalingModel has no consumers,
        so a green '(measured)' next to it implies it shaped the plan."""
        import inspect

        from chimeraforge.commands import measure as measure_cmd

        src = inspect.getsource(measure_cmd)
        assert "not used by the planner" in src
        assert "[green](measured)[/]  -> serial s=" not in src

    def test_the_engine_really_does_ignore_it(self):
        """If this ever stops being true, the label above should change back."""
        import inspect

        from chimeraforge.planner import engine

        src = inspect.getsource(engine.enumerate_candidates)
        assert "eta = 1.0" in src
        assert "scaling_model" not in src
