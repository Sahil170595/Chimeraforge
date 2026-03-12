"""TR133 — Validation and analysis for fitted predictive models.

Computes RMSE, MAE, MAPE, R², and CI calibration for each of the 6
predictive models against a held-out validation set.

Usage:
    python research/tr133/analyze.py [-v]
    (or invoked by run.py Phase 5)
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
import sys

import numpy as np

_DIR = Path(__file__).resolve().parent
_REPO = _DIR.parents[1]
sys.path.insert(0, str(_REPO))

from research.tr133.shared.data_loader import PlannerDataset
from research.tr133.shared.models import PlannerModels, load_models
from research.tr133.shared.utils import TR133_RESULTS, find_latest_run

log = logging.getLogger("tr133.analyze")


# ── Metric helpers ────────────────────────────────────────────────────


def _rmse(actual: np.ndarray, predicted: np.ndarray) -> float:
    return float(np.sqrt(np.mean((actual - predicted) ** 2)))


def _mae(actual: np.ndarray, predicted: np.ndarray) -> float:
    return float(np.mean(np.abs(actual - predicted)))


def _mape(actual: np.ndarray, predicted: np.ndarray) -> float:
    mask = actual != 0
    if not mask.any():
        return 0.0
    return float(np.mean(np.abs((actual[mask] - predicted[mask]) / actual[mask])))


def _r_squared(actual: np.ndarray, predicted: np.ndarray) -> float:
    ss_res = float(np.sum((actual - predicted) ** 2))
    ss_tot = float(np.sum((actual - np.mean(actual)) ** 2))
    if ss_tot == 0:
        return 1.0 if ss_res == 0 else 0.0
    return 1.0 - ss_res / ss_tot


def _compute_metrics(actual: list[float], predicted: list[float]) -> dict:
    """Compute all regression metrics."""
    if len(actual) < 2:
        return {"n": len(actual), "status": "insufficient_data"}
    a = np.array(actual)
    p = np.array(predicted)
    return {
        "n": len(actual),
        "rmse": round(_rmse(a, p), 4),
        "mae": round(_mae(a, p), 4),
        "mape": round(_mape(a, p), 4),
        "r_squared": round(_r_squared(a, p), 4),
        "actual_mean": round(float(np.mean(a)), 4),
        "predicted_mean": round(float(np.mean(p)), 4),
    }


# ── Per-model validation ─────────────────────────────────────────────


def validate_vram(models: PlannerModels, val_ds: PlannerDataset) -> dict:
    """Validate VRAM predictions against held-out data.

    Groups by (model, context_length) and compares predicted vs actual
    mean VRAM — reduces per-measurement noise.
    """
    groups: dict[str, list[float]] = {}
    for r in val_ds.vram:
        key = f"{r.model}|{r.context_length}"
        groups.setdefault(key, []).append(r.vram_peak_mb / 1024)

    actual, predicted = [], []
    for key, vals in groups.items():
        model, ctx_str = key.split("|")
        # TR127 data is all FP16 — validate against FP16 predictions
        pred_gb = models.vram.predict(model, "FP16", context_length=int(ctx_str))
        actual.append(float(np.mean(vals)))
        predicted.append(pred_gb)

    metrics = _compute_metrics(actual, predicted)
    log.info(
        "VRAM validation: R²=%.3f, RMSE=%.3f GB (n=%d groups)",
        metrics.get("r_squared", 0),
        metrics.get("rmse", 0),
        metrics.get("n", 0),
    )
    return metrics


def validate_throughput(models: PlannerModels, val_ds: PlannerDataset) -> dict:
    """Validate throughput predictions against held-out data."""
    actual, predicted = [], []
    for r in val_ds.throughput:
        if r.n_agents != 1:
            continue
        pred = models.throughput.predict(r.model, r.backend, r.quant)
        actual.append(r.tok_per_s)
        predicted.append(pred)
    metrics = _compute_metrics(actual, predicted)
    log.info(
        "Throughput validation: R²=%.3f, RMSE=%.3f tok/s (n=%d)",
        metrics.get("r_squared", 0),
        metrics.get("rmse", 0),
        metrics.get("n", 0),
    )
    return metrics


def validate_quality(models: PlannerModels, val_ds: PlannerDataset) -> dict:
    """Validate quality predictions against held-out data."""
    actual, predicted = [], []
    for r in val_ds.quality:
        pred = models.quality.predict(r.model, r.quant)
        actual.append(r.composite_quality)
        predicted.append(pred)
    metrics = _compute_metrics(actual, predicted)
    # Note: with small n (lookup table model), RMSE is more informative than R²
    metrics["n_lookup_entries"] = len(models.quality.lookup)
    metrics["n_fp16_baselines"] = len(models.quality.fp16_baselines)
    log.info(
        "Quality validation: R²=%.3f, RMSE=%.3f (n=%d, lookup=%d entries)",
        metrics.get("r_squared", 0),
        metrics.get("rmse", 0),
        metrics.get("n", 0),
        metrics.get("n_lookup_entries", 0),
    )
    return metrics


def validate_latency(models: PlannerModels, val_ds: PlannerDataset) -> dict:
    """Validate latency predictions against held-out N=1 data.

    Groups by (model, backend) and compares predicted median service time
    against actual median wall_ms — reduces noise from per-request variance.
    """
    groups: dict[str, list[float]] = {}
    for r in val_ds.latency:
        if r.n_parallel != 1:
            continue
        key = f"{r.model}|{r.backend}"
        groups.setdefault(key, []).append(r.wall_ms)

    actual, predicted = [], []
    for key, vals in groups.items():
        model, backend = key.split("|")
        pred = models.latency.predict_p95(
            model,
            backend,
            request_rate=0.01,
            n_agents=1,
        )
        actual.append(float(np.median(vals)))
        predicted.append(pred["service_ms"])

    metrics = _compute_metrics(actual, predicted)
    log.info(
        "Latency validation: MAPE=%.3f, RMSE=%.1f ms (n=%d groups)",
        metrics.get("mape", 0),
        metrics.get("rmse", 0),
        metrics.get("n", 0),
    )
    return metrics


def validate_scaling(models: PlannerModels, val_ds: PlannerDataset) -> dict:
    """Validate scaling predictions against held-out throughput at N>1."""
    actual_eta, predicted_eta = [], []
    # Group val throughput by (model, backend) to compute eta
    baselines: dict[str, list[float]] = {}
    for r in val_ds.throughput:
        if r.n_agents == 1:
            key = f"{r.model}|{r.backend}"
            baselines.setdefault(key, []).append(r.tok_per_s)

    baseline_means = {k: float(np.mean(v)) for k, v in baselines.items()}

    for r in val_ds.throughput:
        if r.n_agents <= 1:
            continue
        key = f"{r.model}|{r.backend}"
        bl = baseline_means.get(key)
        if bl and bl > 0:
            actual_eta.append(r.tok_per_s / bl)
            predicted_eta.append(
                models.scaling.predict_eta(r.model, r.backend, r.n_agents)
            )

    metrics = _compute_metrics(actual_eta, predicted_eta)
    log.info(
        "Scaling validation: R²=%.3f, MAPE=%.3f (n=%d)",
        metrics.get("r_squared", 0),
        metrics.get("mape", 0),
        metrics.get("n", 0),
    )
    return metrics


# ── Spot checks ───────────────────────────────────────────────────────


def run_spot_checks(models: PlannerModels) -> list[dict]:
    """Verify specific known data points from across TRs."""
    checks = []

    # VRAM: llama3.2-3b FP16 should need ~4-10 GB (weights + overhead + KV)
    vram = models.vram.predict("llama3.2-3b", "FP16", 2048)
    checks.append(
        {
            "check": "llama3.2-3b FP16 VRAM at ctx=2048",
            "predicted": round(vram, 2),
            "expected_range": [3.0, 12.0],
            "pass": 3.0 <= vram <= 12.0,
        }
    )

    # VRAM: llama3.1-8b FP16 should need ~10-28 GB (weights + overhead + KV)
    vram8b = models.vram.predict("llama3.1-8b", "FP16", 2048)
    checks.append(
        {
            "check": "llama3.1-8b FP16 VRAM at ctx=2048",
            "predicted": round(vram8b, 2),
            "expected_range": [8.0, 30.0],
            "pass": 8.0 <= vram8b <= 30.0,
        }
    )

    # VRAM: Q4_K_M should use less VRAM than FP16
    vram_q4 = models.vram.predict("llama3.2-3b", "Q4_K_M", 2048)
    checks.append(
        {
            "check": "Q4_K_M VRAM < FP16 VRAM (llama3.2-3b)",
            "predicted_q4": round(vram_q4, 2),
            "predicted_fp16": round(vram, 2),
            "pass": vram_q4 < vram,
        }
    )

    # Throughput: larger model should be slower
    tps_1b = models.throughput.predict("llama3.2-1b", "ollama", "FP16")
    tps_3b = models.throughput.predict("llama3.2-3b", "ollama", "FP16")
    checks.append(
        {
            "check": "1b faster than 3b (Ollama FP16)",
            "tps_1b": round(tps_1b, 1),
            "tps_3b": round(tps_3b, 1),
            "pass": tps_1b > tps_3b,
        }
    )

    # Quality: FP16 should be >= Q2_K
    q_fp16 = models.quality.predict("llama3.2-1b", "FP16")
    q_q2 = models.quality.predict("llama3.2-1b", "Q2_K")
    checks.append(
        {
            "check": "FP16 quality >= Q2_K quality (llama3.2-1b)",
            "q_fp16": round(q_fp16, 3),
            "q_q2": round(q_q2, 3),
            "pass": q_fp16 >= q_q2,
        }
    )

    # Scaling: eta(1) should be 1.0
    eta1 = models.scaling.predict_eta("llama3.2-3b", "ollama", 1)
    checks.append(
        {
            "check": "eta(N=1) == 1.0",
            "predicted": round(eta1, 4),
            "pass": abs(eta1 - 1.0) < 0.001,
        }
    )

    # Scaling: eta(8) should be < eta(1)
    eta8 = models.scaling.predict_eta("llama3.2-3b", "ollama", 8)
    checks.append(
        {
            "check": "eta(N=8) < eta(N=1) for Ollama",
            "eta_8": round(eta8, 4),
            "pass": eta8 < 1.0,
        }
    )

    # Cost: higher throughput = lower cost per token
    cost_fast = models.cost.predict_cost_per_1m(100.0)
    cost_slow = models.cost.predict_cost_per_1m(10.0)
    checks.append(
        {
            "check": "Higher throughput = lower cost per token",
            "cost_at_100tps": round(cost_fast, 4),
            "cost_at_10tps": round(cost_slow, 4),
            "pass": cost_fast < cost_slow,
        }
    )

    # Cost: verify formula against manual calculation
    # At 50 tok/s, $0.035/hr: cost_per_tok = 0.035 / (50*3600) = 1.944e-7
    # cost_per_1M = 1.944e-7 * 1e6 = $0.1944
    expected_1m = 0.035 / (50.0 * 3600) * 1_000_000
    actual_1m = models.cost.predict_cost_per_1m(50.0, hw_cost_hr=0.035)
    checks.append(
        {
            "check": "Cost formula matches manual calculation",
            "predicted": round(actual_1m, 4),
            "expected": round(expected_1m, 4),
            "pass": abs(actual_1m - expected_1m) < 0.001,
        }
    )

    # Cost: monthly cost is hw_rate * 720 hours
    monthly = models.cost.predict_monthly(hw_cost_hr=0.035)
    checks.append(
        {
            "check": "Monthly cost = $0.035/hr * 720h = $25.20",
            "predicted": round(monthly, 2),
            "expected": 25.20,
            "pass": abs(monthly - 25.20) < 0.01,
        }
    )

    passed = sum(1 for c in checks if c["pass"])
    log.info("Spot checks: %d/%d passed", passed, len(checks))
    return checks


# ── Main analysis ─────────────────────────────────────────────────────


def run_analysis(
    run_dir: Path,
    cfg: dict,
    models: PlannerModels | None = None,
    val_ds: PlannerDataset | None = None,
) -> dict:
    """Run full validation and save analysis.json."""
    # Load models if not provided
    if models is None:
        models_path = run_dir / "fitted_models.json"
        if not models_path.exists():
            log.error("No fitted_models.json in %s", run_dir)
            return {"status": "no_models"}
        models = load_models(models_path)

    # Load validation data if not provided
    if val_ds is None:
        from research.tr133.shared.data_loader import load_all, train_val_split

        dataset = load_all(cfg)
        seed = cfg.get("validation", {}).get("random_seed", 42)
        train_frac = cfg.get("validation", {}).get("train_fraction", 0.80)
        val_ds = PlannerDataset()
        for attr in ["throughput", "quality", "vram", "latency", "cost", "scaling"]:
            _, val = train_val_split(
                getattr(dataset, attr),
                train_frac=train_frac,
                seed=seed,
            )
            setattr(val_ds, attr, val)

    # Run validations
    vram_metrics = validate_vram(models, val_ds)
    throughput_metrics = validate_throughput(models, val_ds)
    quality_metrics = validate_quality(models, val_ds)
    latency_metrics = validate_latency(models, val_ds)
    scaling_metrics = validate_scaling(models, val_ds)

    # Spot checks
    spot_checks = run_spot_checks(models)

    # Check against targets
    targets = cfg.get("validation", {}).get("targets", {})
    target_results = {}
    for name, metric_key, threshold, above in [
        ("throughput_r2", "r_squared", targets.get("throughput_r2", 0.85), True),
        ("vram_r2", "r_squared", targets.get("vram_r2", 0.95), True),
        ("quality_rmse", "rmse", targets.get("quality_rmse", 0.10), False),
        ("latency_mape", "mape", targets.get("latency_mape", 0.25), False),
    ]:
        metrics_map = {
            "throughput_r2": throughput_metrics,
            "vram_r2": vram_metrics,
            "quality_rmse": quality_metrics,
            "latency_mape": latency_metrics,
        }
        val = metrics_map[name].get(metric_key, 0)
        passed = val >= threshold if above else val <= threshold
        target_results[name] = {
            "target": threshold,
            "actual": val,
            "passed": passed,
        }

    all_targets_met = all(t["passed"] for t in target_results.values())
    spot_pass_rate = (
        sum(1 for c in spot_checks if c["pass"]) / len(spot_checks)
        if spot_checks
        else 0
    )

    analysis = {
        "summary": {
            "all_targets_met": all_targets_met,
            "spot_check_pass_rate": round(spot_pass_rate, 2),
            "n_spot_checks": len(spot_checks),
        },
        "targets": target_results,
        "vram": vram_metrics,
        "throughput": throughput_metrics,
        "quality": quality_metrics,
        "latency": latency_metrics,
        "scaling": scaling_metrics,
        "spot_checks": spot_checks,
    }

    out_path = run_dir / "validation.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(analysis, f, indent=2, default=str)

    log.info("Validation saved to %s", out_path)
    log.info("  All targets met: %s", all_targets_met)
    for name, result in target_results.items():
        status = "PASS" if result["passed"] else "FAIL"
        log.info(
            "  %s: %.3f (target: %.3f) [%s]",
            name,
            result["actual"],
            result["target"],
            status,
        )

    return analysis


def main() -> int:
    parser = argparse.ArgumentParser(description="TR133 validation analysis")
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument("--config", default=str(_DIR / "config.yaml"))
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s  %(message)s",
    )

    import yaml

    with open(args.config, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    run_dir = find_latest_run(TR133_RESULTS)
    if run_dir is None:
        log.error("No run directory found in %s", TR133_RESULTS)
        return 1

    run_analysis(run_dir, cfg)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
