"""Refit planner coefficients from benchmark result JSON files.

Extracts throughput lookups, quant multipliers, service times, and
optionally re-fits the size power-law from bench measurements, then
merges them into the existing fitted_models.json structure.
"""

from __future__ import annotations

import json
import logging
import statistics
from collections import defaultdict
from pathlib import Path

from chimeraforge.planner.constants import MODEL_PARAMS_B

log = logging.getLogger("chimeraforge.refit")


# ---------------------------------------------------------------------------
# Load
# ---------------------------------------------------------------------------


def load_bench_results(paths: list[Path]) -> list[dict]:
    """Load and concatenate bench JSON files.

    Each file is expected to contain a JSON array of result dicts
    (the format produced by ``chimeraforge bench``).

    Raises:
        FileNotFoundError: If any path does not exist.
    """
    all_results: list[dict] = []
    for p in paths:
        with open(p, encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            all_results.extend(data)
        else:
            all_results.append(data)
    return all_results


# ---------------------------------------------------------------------------
# Extract
# ---------------------------------------------------------------------------


def extract_throughput_lookup(results: list[dict]) -> dict[str, float]:
    """Extract throughput entries from bench results.

    Returns:
        Dict mapping ``'{model}|{backend}|{quant}'`` to mean tok/s.
        Uses ``'FP16'`` as the quant key when the result has no quant.
    """
    lookup: dict[str, float] = {}
    for r in results:
        model = r.get("model", "")
        backend = r.get("backend", "")
        quant = r.get("quant") or "FP16"
        agg = r.get("aggregate", {})
        tps_info = agg.get("throughput_tps", {})
        mean_tps = tps_info.get("mean")
        if mean_tps is not None and mean_tps > 0:
            key = f"{model}|{backend}|{quant}"
            lookup[key] = mean_tps
    return lookup


def extract_quant_multipliers(
    results: list[dict],
    existing: dict[str, float],
) -> dict[str, float]:
    """Compute quant multipliers from paired FP16/quantized measurements.

    For each ``(model, backend)`` pair that has both an FP16 and a quantized
    result, computes ``ratio = quant_tps / fp16_tps``.  Averages ratios
    across all such pairs per quant level.

    Falls back to *existing* multipliers for quant levels without paired data.
    """
    # Group throughputs by (model, backend)
    by_mb: dict[str, dict[str, float]] = defaultdict(dict)
    for r in results:
        model = r.get("model", "")
        backend = r.get("backend", "")
        quant = r.get("quant") or "FP16"
        agg = r.get("aggregate", {})
        mean_tps = agg.get("throughput_tps", {}).get("mean")
        if mean_tps is not None and mean_tps > 0:
            mb = f"{model}|{backend}"
            by_mb[mb][quant] = mean_tps

    # Compute ratios where FP16 baseline exists
    ratios_per_quant: dict[str, list[float]] = defaultdict(list)
    for mb, quants in by_mb.items():
        fp16_tps = quants.get("FP16")
        if fp16_tps is None or fp16_tps <= 0:
            continue
        for q, tps in quants.items():
            if q == "FP16":
                continue
            ratios_per_quant[q].append(tps / fp16_tps)

    # Average ratios; fall back to existing
    merged = dict(existing)
    merged["FP16"] = 1.0
    for q, ratios in ratios_per_quant.items():
        merged[q] = statistics.mean(ratios)
    return merged


def extract_service_times(results: list[dict]) -> dict[str, float]:
    """Extract latency service times from bench results.

    Returns:
        Dict mapping ``'{model}|{backend}'`` to mean total_duration_ms,
        averaged across quant levels.
    """
    buckets: dict[str, list[float]] = defaultdict(list)
    for r in results:
        model = r.get("model", "")
        backend = r.get("backend", "")
        agg = r.get("aggregate", {})
        dur = agg.get("total_duration_ms", {}).get("mean")
        if dur is not None and dur > 0:
            key = f"{model}|{backend}"
            buckets[key].append(dur)
    return {k: statistics.mean(v) for k, v in buckets.items()}


# ---------------------------------------------------------------------------
# Fit
# ---------------------------------------------------------------------------


def fit_power_law(
    throughputs: dict[str, float],
    model_params: dict[str, float] | None = None,
) -> tuple[float, float]:
    """Fit ``tps = a * params^(-b)`` from FP16 throughputs.

    Uses :func:`scipy.optimize.curve_fit` when available.
    Returns ``(a, b)`` or defaults ``(100.0, 0.5)`` if fewer than 3 FP16
    data points or scipy is not installed.
    """
    params_db = model_params or MODEL_PARAMS_B

    # Collect (params_B, tps) pairs for FP16 entries
    points: list[tuple[float, float]] = []
    for key, tps in throughputs.items():
        parts = key.split("|")
        if len(parts) >= 3 and parts[2] == "FP16":
            model = parts[0]
            p = params_db.get(model)
            if p is not None:
                points.append((p, tps))

    if len(points) < 3:
        return (100.0, 0.5)

    try:
        from scipy.optimize import curve_fit  # type: ignore[import-untyped]

        xs = [p[0] for p in points]
        ys = [p[1] for p in points]

        def _power(x: float, a: float, b: float) -> float:
            return a * x ** (-b)

        (a, b), _ = curve_fit(_power, xs, ys, p0=[100.0, 0.5], maxfev=5000)
        return (float(a), float(b))
    except Exception:
        log.warning("scipy curve_fit unavailable or failed; using defaults")
        return (100.0, 0.5)


# ---------------------------------------------------------------------------
# Merge
# ---------------------------------------------------------------------------


def merge_fitted_models(
    existing: dict,
    throughput_lookup: dict[str, float],
    quant_multipliers: dict[str, float],
    service_times: dict[str, float],
    power_law: tuple[float, float] | None,
) -> dict:
    """Merge new measurements into the existing fitted_models dict.

    New entries override existing; entries not in the new data are preserved.
    Sets ``fitted=True`` on updated sections.
    """
    merged = json.loads(json.dumps(existing))  # deep copy

    # Throughput
    tp = merged.setdefault("throughput", {})
    tp_lookup = tp.setdefault("lookup", {})
    tp_lookup.update(throughput_lookup)
    tp["quant_multipliers"] = quant_multipliers
    if power_law is not None:
        tp["size_power_a"] = power_law[0]
        tp["size_power_b"] = power_law[1]
    tp["fitted"] = True

    # Latency service times
    lat = merged.setdefault("latency", {})
    st = lat.setdefault("service_times", {})
    st.update(service_times)
    lat["fitted"] = True

    return merged


# ---------------------------------------------------------------------------
# Orchestrate
# ---------------------------------------------------------------------------


def refit_from_bench(
    bench_paths: list[Path],
    base_models_path: Path | None = None,
) -> tuple[dict, dict]:
    """Top-level refit orchestrator.

    1. Load bench results from *bench_paths*.
    2. Load existing fitted_models (bundled or from *base_models_path*).
    3. Extract throughput lookup, quant multipliers, service times.
    4. Fit power law (if enough FP16 data).
    5. Merge into existing.

    Returns:
        ``(merged_dict, summary_dict)`` where *summary* reports counts of
        updated entries and any warnings.
    """
    results = load_bench_results(bench_paths)

    # Load base
    if base_models_path is not None:
        with open(base_models_path, encoding="utf-8") as f:
            existing = json.load(f)
    else:
        import importlib.resources as pkg_resources

        data_dir = pkg_resources.files("chimeraforge.planner") / "data"
        models_file = data_dir / "fitted_models.json"
        with pkg_resources.as_file(models_file) as p:
            with open(p, encoding="utf-8") as f:
                existing = json.load(f)

    tp_lookup = extract_throughput_lookup(results)
    existing_qm = existing.get("throughput", {}).get("quant_multipliers", {})
    qm = extract_quant_multipliers(results, existing_qm)
    st = extract_service_times(results)
    pl = fit_power_law(tp_lookup)

    merged = merge_fitted_models(existing, tp_lookup, qm, st, pl)

    # Build summary
    warnings: list[str] = []
    for r in results:
        runs = r.get("individual_runs", [])
        if len(runs) > 1:
            tps_vals = [run.get("throughput_tps", 0) for run in runs]
            mean_tps = statistics.mean(tps_vals) if tps_vals else 0
            if mean_tps > 0:
                cv = statistics.stdev(tps_vals) / mean_tps
                if cv > 0.3:
                    model = r.get("model", "?")
                    quant = r.get("quant") or "FP16"
                    warnings.append(
                        f"High CV ({cv:.2f}) for {model}|{quant} — results may be noisy"
                    )

    summary = {
        "bench_results_loaded": len(results),
        "throughput_entries_updated": len(tp_lookup),
        "quant_multipliers_updated": len(qm),
        "service_times_updated": len(st),
        "power_law_refit": pl != (100.0, 0.5),
        "warnings": warnings,
    }

    return merged, summary


def save_fitted_models(data: dict, output_path: Path) -> Path:
    """Write merged fitted_models.json to *output_path*.

    Creates parent directories if needed. Returns the resolved path.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(data, indent=2))
    return output_path
