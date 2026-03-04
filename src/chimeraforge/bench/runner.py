"""Benchmark runner -- orchestrates backend calls and collects metrics.

Supports three workload profiles (single/batch/server) and two sweep
modes (quantization sweep, context-length sweep). Results are persisted
as JSON for later analysis or planner refit.
"""

from __future__ import annotations

import asyncio
import json
import logging
import random
import statistics
from pathlib import Path
from typing import Callable

from chimeraforge.bench.backends import get_backend
from chimeraforge.bench.backends.base import Backend
from chimeraforge.bench.metrics import (
    BenchmarkResult,
    RunMetrics,
    aggregate_runs,
    collect_environment,
    now_iso,
    result_to_dict,
)
from chimeraforge.bench.profiles import get_profile
from chimeraforge.bench.prompts import DEFAULT_PROMPT

logger = logging.getLogger(__name__)


async def _run_single(
    backend: Backend,
    model: str,
    prompt: str,
    options: dict | None,
    total: int,
    on_progress: Callable[[int, int], None] | None = None,
) -> tuple[list[RunMetrics], list[str]]:
    """Sequential execution -- one request at a time."""
    results: list[RunMetrics] = []
    warnings: list[str] = []
    for i in range(total):
        try:
            metrics = await backend.generate(model, prompt, options)
            results.append(metrics)
        except Exception as exc:
            warnings.append(f"Run {i + 1}/{total} failed: {exc}")
            logger.warning("Run %d/%d failed: %s", i + 1, total, exc)
        if on_progress:
            on_progress(i + 1, total)
    return results, warnings


async def _run_batch(
    backend: Backend,
    model: str,
    prompt: str,
    options: dict | None,
    total: int,
    concurrency: int,
    on_progress: Callable[[int, int], None] | None = None,
) -> tuple[list[RunMetrics], list[str]]:
    """Concurrent batch execution -- fires `concurrency` requests at a time."""
    results: list[RunMetrics] = []
    warnings: list[str] = []
    completed = 0
    for batch_start in range(0, total, concurrency):
        batch_size = min(concurrency, total - batch_start)
        coros = [backend.generate(model, prompt, options) for _ in range(batch_size)]
        batch_results = await asyncio.gather(*coros, return_exceptions=True)
        for j, r in enumerate(batch_results):
            idx = batch_start + j + 1
            if isinstance(r, Exception):
                warnings.append(f"Run {idx}/{total} failed: {r}")
                logger.warning("Run %d/%d failed: %s", idx, total, r)
            else:
                results.append(r)
        completed += batch_size
        if on_progress:
            on_progress(completed, total)
    return results, warnings


async def _run_server(
    backend: Backend,
    model: str,
    prompt: str,
    options: dict | None,
    total: int,
    concurrency: int,
    arrival_rate: float,
    on_progress: Callable[[int, int], None] | None = None,
) -> tuple[list[RunMetrics], list[str]]:
    """Poisson-arrival server simulation -- requests arrive at `arrival_rate` req/s."""
    sem = asyncio.Semaphore(concurrency)
    results: list[RunMetrics] = []
    warnings: list[str] = []
    lock = asyncio.Lock()
    completed = 0

    async def _one_request(idx: int) -> None:
        nonlocal completed
        try:
            async with sem:
                metrics = await backend.generate(model, prompt, options)
            async with lock:
                results.append(metrics)
        except Exception as exc:
            async with lock:
                warnings.append(f"Run {idx}/{total} failed: {exc}")
                logger.warning("Run %d/%d failed: %s", idx, total, exc)
        finally:
            async with lock:
                completed += 1
                if on_progress:
                    on_progress(completed, total)

    tasks: list[asyncio.Task] = []
    for i in range(total):
        tasks.append(asyncio.create_task(_one_request(i + 1)))
        # Poisson inter-arrival: exponential distribution
        delay = random.expovariate(arrival_rate)
        await asyncio.sleep(delay)

    await asyncio.gather(*tasks)
    return results, warnings


async def run_benchmark(
    model: str,
    backend_name: str,
    quant: str | None = None,
    workload: str = "single",
    runs: int = 5,
    rate: float | None = None,
    context_length: int = 2048,
    base_url: str | None = None,
    prompt: str | None = None,
    options: dict | None = None,
    on_progress: Callable[[int, int], None] | None = None,
) -> BenchmarkResult:
    """Run a complete benchmark for one configuration.

    Args:
        model: Model name or tag (e.g. "llama3.2-3b", "gemma3:latest").
        backend_name: Backend identifier ("ollama", "vllm", "tgi").
        quant: Optional quantization level (e.g. "Q4_K_M").
        workload: Workload profile name ("single", "batch", "server").
        runs: Number of benchmark runs (overrides profile default).
        rate: Request rate for server workload (req/s).
        context_length: Context window length in tokens.
        base_url: Backend URL override.
        prompt: Custom prompt (default: PROMPT_MEDIUM).
        options: Additional backend-specific generation options.
        on_progress: Callback(completed, total) for progress tracking.

    Returns:
        BenchmarkResult with individual and aggregate metrics.

    Raises:
        RuntimeError: If backend health check or model check fails.
    """
    # Create backend
    backend_kwargs: dict = {}
    if base_url:
        backend_kwargs["base_url"] = base_url
    backend = get_backend(backend_name, **backend_kwargs)

    # Pre-flight: health check
    ok, msg = await backend.health_check()
    if not ok:
        raise RuntimeError(msg)

    # Pre-flight: model check
    ok, msg = await backend.check_model(model)
    if not ok:
        raise RuntimeError(msg)

    # Get backend version for environment info
    backend_version = await backend.get_version()

    # Build effective prompt
    effective_prompt = prompt or DEFAULT_PROMPT

    # Build options with context length
    effective_options = dict(options) if options else {}
    if backend_name == "ollama":
        effective_options.setdefault("num_ctx", context_length)

    # Get workload profile
    profile = get_profile(workload, rate=rate, runs=runs)

    # Collect environment
    env = collect_environment(backend_name, backend_version)

    # Execute workload
    warnings: list[str] = []
    logger.info(
        "Starting %s benchmark: model=%s, backend=%s, runs=%d",
        profile.name,
        model,
        backend_name,
        profile.total_requests,
    )

    if profile.name == "single":
        run_results, run_warnings = await _run_single(
            backend,
            model,
            effective_prompt,
            effective_options,
            profile.total_requests,
            on_progress,
        )
    elif profile.name == "batch":
        run_results, run_warnings = await _run_batch(
            backend,
            model,
            effective_prompt,
            effective_options,
            profile.total_requests,
            profile.concurrency,
            on_progress,
        )
    elif profile.name == "server":
        arr_rate = (
            profile.arrival_rate if profile.arrival_rate and profile.arrival_rate > 0 else 1.0
        )
        run_results, run_warnings = await _run_server(
            backend,
            model,
            effective_prompt,
            effective_options,
            profile.total_requests,
            profile.concurrency,
            arr_rate,
            on_progress,
        )
    else:
        raise ValueError(f"Unknown workload profile: {profile.name}")

    warnings.extend(run_warnings)

    if not run_results:
        raise RuntimeError(
            f"All {profile.total_requests} benchmark runs failed. "
            f"Errors: {'; '.join(run_warnings[:3])}"
        )

    # Check for anomalies using real CV (stddev / mean)
    throughputs = [r.throughput_tps for r in run_results]
    if len(throughputs) > 1:
        mean_tps = statistics.mean(throughputs)
        if mean_tps > 0:
            cv = statistics.stdev(throughputs) / mean_tps
            if cv > 0.3:
                warnings.append(f"High throughput variance (CV={cv:.2f}). Results may be noisy.")

    # Warn about unmeasurable TTFT
    ttfts = [r.ttft_ms for r in run_results]
    if any(t < 0 for t in ttfts):
        warnings.append(f"TTFT not measurable with {backend_name} non-streaming API.")

    # Aggregate
    agg = aggregate_runs(run_results)

    return BenchmarkResult(
        model=model,
        backend=backend_name,
        quant=quant,
        workload=profile.name,
        runs=profile.total_requests,
        context_length=context_length,
        individual_runs=run_results,
        aggregate=agg,
        environment=env,
        timestamp=now_iso(),
        warnings=warnings,
    )


async def run_quant_sweep(
    model: str,
    backend_name: str,
    quants: list[str] | None = None,
    **kwargs: object,
) -> list[BenchmarkResult]:
    """Run benchmarks across quantization levels."""
    from chimeraforge.planner.constants import QUANT_LEVELS

    levels = quants or QUANT_LEVELS
    results: list[BenchmarkResult] = []
    for q in levels:
        logger.info("Quant sweep: %s @ %s", model, q)
        result = await run_benchmark(model=model, backend_name=backend_name, quant=q, **kwargs)
        results.append(result)
    return results


async def run_context_sweep(
    model: str,
    backend_name: str,
    context_lengths: list[int],
    **kwargs: object,
) -> list[BenchmarkResult]:
    """Run benchmarks across context lengths."""
    results: list[BenchmarkResult] = []
    for ctx in context_lengths:
        logger.info("Context sweep: %s @ ctx=%d", model, ctx)
        result = await run_benchmark(
            model=model,
            backend_name=backend_name,
            context_length=ctx,
            **kwargs,
        )
        results.append(result)
    return results


def save_results(results: list[BenchmarkResult], output_dir: Path) -> Path:
    """Persist benchmark results as JSON.

    Args:
        results: List of BenchmarkResult objects.
        output_dir: Directory to write to (created if needed).

    Returns:
        Path to the saved JSON file.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = results[0].timestamp.replace(":", "-").replace("+", "_") if results else "empty"
    filename = f"bench_{timestamp}.json"
    path = output_dir / filename

    data = [result_to_dict(r) for r in results]
    path.write_text(json.dumps(data, indent=2))
    logger.info("Results saved to %s", path)
    return path
