"""Statistical analysis for benchmark results and prediction accuracy.

Provides standalone functions for computing RMSE, MAE, MAPE, and
R-squared between predicted and actual values, plus a helper to
extract summary rows from bench result dicts.

All functions use only the standard library (math, statistics).
"""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass


@dataclass
class AnalysisStats:
    """Statistical summary of prediction accuracy or benchmark comparison.

    Attributes:
        rmse: Root mean squared error.
        mae: Mean absolute error.
        mape: Mean absolute percentage error (0-1 scale).
        r_squared: Coefficient of determination.
        n_samples: Number of data points used.
    """

    rmse: float
    mae: float
    mape: float
    r_squared: float
    n_samples: int


def compute_rmse(actual: list[float], predicted: list[float]) -> float:
    """Compute root mean squared error.

    Args:
        actual: Observed values.
        predicted: Predicted values (same length as *actual*).

    Returns:
        RMSE value. Returns 0.0 for empty inputs.

    Raises:
        ValueError: If lists differ in length.
    """
    if len(actual) != len(predicted):
        raise ValueError(f"Length mismatch: actual={len(actual)}, predicted={len(predicted)}")
    if not actual:
        return 0.0
    mse = statistics.mean((a - p) ** 2 for a, p in zip(actual, predicted))
    return math.sqrt(mse)


def compute_mae(actual: list[float], predicted: list[float]) -> float:
    """Compute mean absolute error.

    Args:
        actual: Observed values.
        predicted: Predicted values (same length as *actual*).

    Returns:
        MAE value. Returns 0.0 for empty inputs.

    Raises:
        ValueError: If lists differ in length.
    """
    if len(actual) != len(predicted):
        raise ValueError(f"Length mismatch: actual={len(actual)}, predicted={len(predicted)}")
    if not actual:
        return 0.0
    return statistics.mean(abs(a - p) for a, p in zip(actual, predicted))


def compute_mape(actual: list[float], predicted: list[float]) -> float:
    """Compute mean absolute percentage error.

    Pairs where ``actual == 0`` are skipped to avoid division by zero.

    Args:
        actual: Observed values.
        predicted: Predicted values (same length as *actual*).

    Returns:
        MAPE as a fraction (0-1). Returns 0.0 when no non-zero actuals exist.

    Raises:
        ValueError: If lists differ in length.
    """
    if len(actual) != len(predicted):
        raise ValueError(f"Length mismatch: actual={len(actual)}, predicted={len(predicted)}")
    if not actual:
        return 0.0
    pct_errors: list[float] = []
    for a, p in zip(actual, predicted):
        if a != 0.0:
            pct_errors.append(abs(a - p) / abs(a))
    if not pct_errors:
        return 0.0
    return statistics.mean(pct_errors)


def compute_r_squared(actual: list[float], predicted: list[float]) -> float:
    """Compute the coefficient of determination (R-squared).

    ``R^2 = 1 - SS_res / SS_tot`` where SS_tot is the total sum of squares
    around the mean of *actual*.

    Args:
        actual: Observed values.
        predicted: Predicted values (same length as *actual*).

    Returns:
        R-squared value. Returns 0.0 for empty inputs or when all actuals
        are identical (SS_tot == 0).

    Raises:
        ValueError: If lists differ in length.
    """
    if len(actual) != len(predicted):
        raise ValueError(f"Length mismatch: actual={len(actual)}, predicted={len(predicted)}")
    if not actual:
        return 0.0
    mean_actual = statistics.mean(actual)
    ss_tot = sum((a - mean_actual) ** 2 for a in actual)
    if ss_tot == 0.0:
        return 0.0
    ss_res = sum((a - p) ** 2 for a, p in zip(actual, predicted))
    return 1.0 - ss_res / ss_tot


def analyze(actual: list[float], predicted: list[float]) -> AnalysisStats:
    """Compute all prediction accuracy metrics at once.

    Args:
        actual: Observed values.
        predicted: Predicted values (same length as *actual*).

    Returns:
        An ``AnalysisStats`` dataclass with RMSE, MAE, MAPE, R-squared,
        and sample count.

    Raises:
        ValueError: If lists differ in length.
    """
    return AnalysisStats(
        rmse=compute_rmse(actual, predicted),
        mae=compute_mae(actual, predicted),
        mape=compute_mape(actual, predicted),
        r_squared=compute_r_squared(actual, predicted),
        n_samples=len(actual),
    )


# ---------------------------------------------------------------------------
# Bench-result summarization
# ---------------------------------------------------------------------------


@dataclass
class BenchSummaryRow:
    """One row in a benchmark summary table.

    Attributes:
        model: Model name or tag.
        backend: Serving backend identifier.
        quant: Quantization level (e.g. "Q4_K_M") or "default".
        workload: Workload profile name.
        context_length: Context window in tokens.
        throughput_mean: Mean throughput in tok/s.
        throughput_p95: p95 throughput in tok/s.
        ttft_mean: Mean time-to-first-token in ms.
        duration_mean: Mean total duration in ms.
        duration_p95: p95 total duration in ms.
        runs: Number of benchmark runs.
    """

    model: str
    backend: str
    quant: str
    workload: str
    context_length: int
    throughput_mean: float
    throughput_p95: float
    ttft_mean: float
    duration_mean: float
    duration_p95: float
    runs: int


def _safe_get_stat(aggregate: dict, metric: str, stat: str) -> float:
    """Safely extract a stat from a nested aggregate dict.

    Args:
        aggregate: The aggregate dict from a bench result.
        metric: Top-level key (e.g. "throughput_tps").
        stat: Stat key (e.g. "mean", "p95").

    Returns:
        The numeric value, or 0.0 if the path is missing.
    """
    metric_dict = aggregate.get(metric)
    if not isinstance(metric_dict, dict):
        return 0.0
    value = metric_dict.get(stat, 0.0)
    if value is None:
        return 0.0
    return float(value)


def summarize_bench_results(results: list[dict]) -> list[BenchSummaryRow]:
    """Extract summary rows from bench result dicts.

    Each dict is expected to follow the ``BenchmarkResult`` schema
    produced by ``chimeraforge.bench.metrics.result_to_dict``.

    Args:
        results: List of bench result dicts.

    Returns:
        A list of ``BenchSummaryRow`` sorted by (model, quant).
    """
    rows: list[BenchSummaryRow] = []
    for r in results:
        agg = r.get("aggregate", {})
        rows.append(
            BenchSummaryRow(
                model=r.get("model", "unknown"),
                backend=r.get("backend", "unknown"),
                quant=r.get("quant") or "default",
                workload=r.get("workload", "single"),
                context_length=int(r.get("context_length", 0)),
                throughput_mean=_safe_get_stat(agg, "throughput_tps", "mean"),
                throughput_p95=_safe_get_stat(agg, "throughput_tps", "p95"),
                ttft_mean=_safe_get_stat(agg, "ttft_ms", "mean"),
                duration_mean=_safe_get_stat(agg, "total_duration_ms", "mean"),
                duration_p95=_safe_get_stat(agg, "total_duration_ms", "p95"),
                runs=int(r.get("runs", 0)),
            )
        )
    rows.sort(key=lambda row: (row.model, row.quant))
    return rows
