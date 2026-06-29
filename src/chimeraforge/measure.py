"""Measure-on-demand: benchmark a live model and fold real numbers into the corpus.

This is the non-toy path for off-registry models. Instead of a roofline guess,
it runs the actual model through the existing ``bench`` machinery, derives real
N=1 throughput, service time, and concurrency scaling, and merges them into a
local ``fitted_models.json`` via the existing ``refit`` loop. ``plan``/``suggest``
then read that corpus automatically, so provenance becomes genuinely *measured*.

Quality is deliberately NOT synthesised here: the planner's quality scale is a
TR benchmark composite, and a quick text-similarity run is a different metric.
Measuring quality properly needs the full eval harness against that benchmark.
"""

from __future__ import annotations

import json
import logging
import tempfile
from dataclasses import dataclass
from pathlib import Path

from chimeraforge.bench.metrics import BenchmarkResult, result_to_dict
from chimeraforge.bench.runner import run_benchmark
from chimeraforge.planner.resolver import ResolverError, measured_corpus_path, resolve_spec
from chimeraforge.refit.fitter import (
    refit_from_bench,
    save_fitted_models,
    serial_fraction_from_eta,
)

log = logging.getLogger("chimeraforge.measure")

DEFAULT_CONCURRENCY = 4  # N at which scaling efficiency is measured
CONCURRENCY_WAVES = 3  # batch total = concurrency * waves


@dataclass
class MeasureResult:
    """Outcome of a measure-on-demand run."""

    model: str
    backend: str
    quant: str
    tps_n1: float
    cv_n1: float
    service_ms: float
    n_concurrent: int | None
    eta_at_n: float | None
    serial_fraction: float | None
    corpus_path: str
    warnings: list[str]


def _cv(result: BenchmarkResult) -> float:
    tps = result.aggregate.throughput_tps
    return (tps.stddev / tps.mean) if tps.mean else 0.0


def fold_into_corpus(
    n1_result: BenchmarkResult,
    serial_key: str | None,
    serial_fraction: float | None,
    corpus_path: Path,
) -> dict:
    """Merge a measured N=1 result (+ optional scaling) into the local corpus.

    Reuses ``refit_from_bench`` for throughput/service-time/quant-multiplier
    extraction and Bayesian blending, then overlays the measured serial fraction
    onto the scaling model. The existing corpus (or bundled data) is the base, so
    repeated measures accumulate. Returns the merged dict (also written to disk).
    """
    base = corpus_path if corpus_path.is_file() else None
    with tempfile.TemporaryDirectory() as td:
        bench_path = Path(td) / "measured.json"
        bench_path.write_text(json.dumps([result_to_dict(n1_result)], indent=2), encoding="utf-8")
        merged, _summary = refit_from_bench([bench_path], base)

    if serial_key and serial_fraction is not None:
        scaling = merged.setdefault("scaling", {})
        sf = scaling.setdefault("serial_fractions", {})
        sf[serial_key] = serial_fraction
        scaling["fitted"] = True

    # Stamp the package version so load_effective_models can warn when the corpus
    # predates an upgrade (its embedded bundled-coefficient snapshot would
    # otherwise silently shadow improved coefficients for un-measured models).
    from chimeraforge import __version__

    merged["_chimeraforge_version"] = __version__
    save_fitted_models(merged, corpus_path)
    return merged


async def measure_model(
    model: str,
    *,
    backend: str = "ollama",
    quant: str | None = None,
    runs: int = 5,
    concurrency: int = DEFAULT_CONCURRENCY,
    context_length: int = 2048,
    base_url: str | None = None,
    ollama_url: str | None = None,
    hf_token: str | None = None,
    corpus_path: Path | None = None,
    on_progress=None,
) -> MeasureResult:
    """Benchmark *model* live and fold real throughput + scaling into the corpus.

    Args:
        model: Identifier to benchmark (Ollama tag / served model name).
        backend: Serving backend ("ollama", "vllm", "tgi").
        quant: Quant label for the lookup key; defaults to the resolved native
            quant, else "FP16". Must match what ``plan`` will pin to.
        runs: N=1 sample count (single workload).
        concurrency: N at which to measure scaling (0/1 to skip scaling).
        corpus_path: Where to write/merge the measured corpus (default: the
            shared measured-corpus path).

    Raises:
        RuntimeError: If the backend/model pre-flight or all runs fail.
    """
    warnings: list[str] = []
    corpus_path = corpus_path or measured_corpus_path()
    eff_base_url = base_url or ollama_url

    # Resolve for the native quant + a clean lookup key; tolerate failure since
    # measurement itself does not need the resolved spec.
    if quant is None:
        try:
            spec = resolve_spec(model, ollama_url=ollama_url, hf_token=hf_token)
            quant = spec.native_quant
        except ResolverError as exc:
            log.warning("could not resolve '%s' for native quant: %s", model, exc)
    quant = quant or "FP16"

    # 1. N=1 single-stream throughput + service time.
    n1 = await run_benchmark(
        model=model,
        backend_name=backend,
        quant=quant,
        workload="single",
        runs=runs,
        context_length=context_length,
        base_url=eff_base_url,
        on_progress=on_progress,
    )
    tps1 = n1.aggregate.throughput_tps.mean
    warnings.extend(n1.warnings)

    # 2. Scaling at N=concurrency (per-agent efficiency under contention).
    eta = None
    serial_fraction = None
    n_used: int | None = None
    if concurrency and concurrency > 1 and tps1 > 0:
        try:
            nk = await run_benchmark(
                model=model,
                backend_name=backend,
                quant=quant,
                workload="batch",
                runs=concurrency * CONCURRENCY_WAVES,
                context_length=context_length,
                base_url=eff_base_url,
                concurrency=concurrency,
                on_progress=on_progress,
            )
            tpsk = nk.aggregate.throughput_tps.mean
            if tpsk > 0:
                eta = min(1.0, tpsk / tps1)
                serial_fraction = serial_fraction_from_eta(eta, concurrency)
                n_used = concurrency
                warnings.extend(w for w in nk.warnings if w not in warnings)
        except RuntimeError as exc:
            warnings.append(f"scaling not measured (concurrent run failed): {exc}")

    # 3. Fold into the local corpus (throughput/service via refit + scaling).
    serial_key = f"{model}|{backend}"
    fold_into_corpus(
        n1, serial_key if serial_fraction is not None else None, serial_fraction, corpus_path
    )

    return MeasureResult(
        model=model,
        backend=backend,
        quant=quant,
        tps_n1=round(tps1, 1),
        cv_n1=round(_cv(n1), 3),
        service_ms=round(n1.aggregate.total_duration_ms.mean, 1),
        n_concurrent=n_used,
        eta_at_n=round(eta, 3) if eta is not None else None,
        serial_fraction=round(serial_fraction, 3) if serial_fraction is not None else None,
        corpus_path=str(corpus_path),
        warnings=warnings,
    )
