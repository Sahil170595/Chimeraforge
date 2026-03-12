"""TR137 shared utilities: data loaders, validation, constants."""

from __future__ import annotations

import json
import logging
import math
from pathlib import Path
import sys

_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from research.tr125.shared.utils import find_latest_run

logger = logging.getLogger("tr137.shared")

# Source experiment result directories
TR134_RESULTS = _REPO_ROOT / "research" / "tr134" / "results" / "phase3"
TR135_RESULTS = _REPO_ROOT / "research" / "tr135" / "results"
TR136_RESULTS = _REPO_ROOT / "research" / "tr136" / "results"

# Analysis filenames per experiment
TR134_ANALYSIS_FILE = "phase3_analysis.json"
TR135_ANALYSIS_FILE = "tr135_analysis.json"
TR136_ANALYSIS_FILE = "tr136_analysis.json"

# Required top-level keys per source analysis (for validation)
TR134_REQUIRED_KEYS = {
    "metadata",
    "group_stats",
    "degradation_slopes",
    "slope_comparisons",
    "power_analysis",
    "critical_thresholds",
}
TR135_REQUIRED_KEYS = {
    "metadata",
    "group_stats",
    "safety_slopes",
    "power_analysis",
}
TR136_REQUIRED_KEYS = {
    "metadata",
    "group_stats",
    "power_analysis",
}

# Models that appear in multiple TRs (cross-validation anchors)
SHARED_MODELS = {
    "llama3.2-1b": {
        "tr134": "llama3.2-1b",
        "tr135": "llama3.2-1b-q4_k_m",
        "tr136": "llama3.2-1b",
    },
    "llama3.2-3b": {
        "tr134": "llama3.2-3b",
        "tr135": "llama3.2-3b-q4_k_m",
        "tr136": "llama3.2-3b",
    },
}

# All models per TR (for completeness tracking)
TR134_MODELS = {"llama3.2-1b", "llama3.2-3b", "mistral-7b", "qwen2.5-7b"}
TR135_MODELS = {"llama3.2-1b-q4_k_m", "llama3.2-3b-q4_k_m", "qwen2.5-3b-q4_k_m"}
TR136_MODELS = {"llama3.2-1b", "llama3.2-3b", "qwen2.5-1.5b"}

# Anchor point for cross-validation
ANCHOR_QUANT = "Q4_K_M"
ANCHOR_N = 1
ANCHOR_BACKEND = "ollama_q4_k_m"

# Safety vs capability task sets
SAFETY_TASKS = {"advbench_refusal", "truthfulqa", "bbq_bias", "jailbreak_amplification"}
CAPABILITY_TASKS = {"mmlu_real", "arc_challenge"}
ALL_TASKS = SAFETY_TASKS | CAPABILITY_TASKS

# Task → metric name mapping (for TR134 slope key lookups)
TASK_METRIC = {
    "advbench_refusal": "refusal_rate",
    "jailbreak_amplification": "refusal_rate",
    "truthfulqa": "truthfulness",
    "bbq_bias": "bias_resistance",
    "mmlu_real": "accuracy",
    "arc_challenge": "accuracy",
}

# Quantization ordering (bits per weight)
QUANT_BPW = {
    "FP16": 16.0,
    "Q8_0": 8.0,
    "Q6_K": 6.5625,
    "Q5_K_M": 5.5,
    "Q4_K_M": 4.5,
    "Q3_K_S": 3.4375,
    "Q2_K": 2.625,
}

BASELINE_TOLERANCE_PP = 5.0

# Risk level thresholds for deployment matrix
RISK_THRESHOLDS = {
    "low": 95.0,  # >= 95% retention
    "moderate": 90.0,  # >= 90%
    "high": 80.0,  # >= 80%
    # below 80% = critical
}

# Model family inference
FAMILY_PREFIXES = {
    "llama": "Llama",
    "mistral": "Mistral",
    "qwen": "Qwen",
    "gemma": "Gemma",
}


def infer_family(model_name: str) -> str:
    """Infer model family from name."""
    lower = model_name.lower()
    for prefix, family in FAMILY_PREFIXES.items():
        if prefix in lower:
            return family
    return "Unknown"


def classify_risk(retention_pct: float) -> str:
    """Classify risk level from safety retention percentage."""
    if retention_pct >= RISK_THRESHOLDS["low"]:
        return "low"
    if retention_pct >= RISK_THRESHOLDS["moderate"]:
        return "moderate"
    if retention_pct >= RISK_THRESHOLDS["high"]:
        return "high"
    return "critical"


def validate_analysis(data: dict, required_keys: set, label: str) -> list[str]:
    """Validate that a loaded analysis has all required keys.

    Returns list of warning strings (empty = valid).
    """
    warnings: list[str] = []
    if not data:
        warnings.append(f"{label}: empty analysis data")
        return warnings

    missing = required_keys - set(data.keys())
    if missing:
        warnings.append(f"{label}: missing keys: {sorted(missing)}")

    meta = data.get("metadata", {})
    if not meta:
        warnings.append(f"{label}: empty metadata")
    else:
        total = meta.get("total_records", 0) or meta.get("total_raw_records", 0)
        if total == 0:
            warnings.append(f"{label}: zero records in metadata")

    gs = data.get("group_stats", {})
    if not gs:
        warnings.append(f"{label}: empty group_stats")

    return warnings


def check_source_completeness() -> dict[str, dict]:
    """Check which source experiments have results available.

    Returns dict of {tr_label: {available, reason/run_dir, ...}}.
    """
    status: dict[str, dict] = {}
    for label, results_dir, analysis_file in [
        ("tr134", TR134_RESULTS, TR134_ANALYSIS_FILE),
        ("tr135", TR135_RESULTS, TR135_ANALYSIS_FILE),
        ("tr136", TR136_RESULTS, TR136_ANALYSIS_FILE),
    ]:
        run_dir = find_latest_run(results_dir)
        if run_dir is None:
            status[label] = {
                "available": False,
                "reason": f"No results in {results_dir}",
            }
            continue
        path = run_dir / analysis_file
        if not path.exists():
            status[label] = {
                "available": False,
                "reason": f"Analysis not found: {path.name}",
                "run_dir": str(run_dir),
            }
            continue
        # Quick size/key check
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            n_keys = len(data)
            total = data.get("metadata", {}).get("total_records", 0) or data.get(
                "metadata", {}
            ).get("total_raw_records", 0)
        except (json.JSONDecodeError, OSError) as e:
            status[label] = {
                "available": False,
                "reason": f"Cannot read {path.name}: {e}",
                "run_dir": str(run_dir),
            }
            continue

        status[label] = {
            "available": True,
            "run_dir": str(run_dir),
            "analysis_file": str(path),
            "n_keys": n_keys,
            "total_records": total,
        }
    return status


def _load_analysis(
    results_dir: Path,
    analysis_file: str,
    run_dir: Path | None,
    label: str,
    required_keys: set | None = None,
) -> dict:
    """Generic loader for a TR analysis JSON with optional validation."""
    if run_dir is None:
        run_dir = find_latest_run(results_dir)
    if run_dir is None:
        logger.warning("No %s results found in %s", label, results_dir)
        return {}
    path = run_dir / analysis_file
    if not path.exists():
        logger.warning("%s analysis not found: %s", label, path)
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger.error("Failed to load %s: %s", label, e)
        return {}

    logger.info("Loaded %s: %d keys from %s", label, len(data), run_dir.name)

    # Validate if required keys provided
    if required_keys:
        warnings = validate_analysis(data, required_keys, label)
        for w in warnings:
            logger.warning(w)

    return data


def load_tr134(run_dir: Path | None = None) -> dict:
    return _load_analysis(
        TR134_RESULTS, TR134_ANALYSIS_FILE, run_dir, "TR134", TR134_REQUIRED_KEYS
    )


def load_tr135(run_dir: Path | None = None) -> dict:
    return _load_analysis(
        TR135_RESULTS, TR135_ANALYSIS_FILE, run_dir, "TR135", TR135_REQUIRED_KEYS
    )


def load_tr136(run_dir: Path | None = None) -> dict:
    return _load_analysis(
        TR136_RESULTS, TR136_ANALYSIS_FILE, run_dir, "TR136", TR136_REQUIRED_KEYS
    )


# ---------------------------------------------------------------------------
# Cross-phase validation (gap #2 — TR126 gold standard pattern)
# ---------------------------------------------------------------------------


def validate_source_status(data: dict, label: str) -> list[str]:
    """Validate that a source TR's analysis completed successfully.

    Checks metadata for completion markers, sufficient records, and
    non-empty result sections. Returns list of warnings.
    """
    warnings: list[str] = []
    meta = data.get("metadata", {})
    if not meta:
        warnings.append(f"{label}: no metadata — cannot verify completion")
        return warnings

    # Check record count
    total = meta.get("total_records", 0) or meta.get("total_raw_records", 0)
    if total < 100:
        warnings.append(f"{label}: only {total} records — results may be unreliable")

    # Check for error markers
    if meta.get("error") or meta.get("failed"):
        warnings.append(f"{label}: source analysis has error/failed markers")

    # Check group_stats is populated
    gs = data.get("group_stats", {})
    if not gs:
        warnings.append(f"{label}: empty group_stats — source may not have completed")

    # Check that slopes/comparisons exist (key analysis outputs)
    if label.upper() == "TR134":
        if not data.get("degradation_slopes"):
            warnings.append(
                f"{label}: no degradation slopes — analysis may be incomplete"
            )
        if not data.get("slope_comparisons"):
            warnings.append(
                f"{label}: no slope comparisons — analysis may be incomplete"
            )
    elif label.upper() == "TR135":
        if not data.get("safety_slopes"):
            warnings.append(f"{label}: no safety slopes — analysis may be incomplete")

    return warnings


# ---------------------------------------------------------------------------
# Outlier detection (gap #3 — TR126 gold standard pattern)
# ---------------------------------------------------------------------------


def detect_outliers_iqr(values: list[float], factor: float = 1.5) -> dict:
    """Detect outliers using the IQR method.

    Returns dict with fence values and outlier indices/values.
    """
    if len(values) < 4:
        return {
            "n_outliers": 0,
            "outlier_indices": [],
            "outlier_values": [],
            "lower_fence": None,
            "upper_fence": None,
            "method": "iqr",
        }

    sorted_vals = sorted(values)
    n = len(sorted_vals)
    q1 = sorted_vals[n // 4]
    q3 = sorted_vals[3 * n // 4]
    iqr = q3 - q1
    lower_fence = q1 - factor * iqr
    upper_fence = q3 + factor * iqr

    outlier_indices = []
    outlier_values = []
    for i, v in enumerate(values):
        if v < lower_fence or v > upper_fence:
            outlier_indices.append(i)
            outlier_values.append(v)

    return {
        "n_outliers": len(outlier_indices),
        "outlier_indices": outlier_indices,
        "outlier_values": [round(v, 4) for v in outlier_values],
        "q1": round(q1, 4),
        "q3": round(q3, 4),
        "iqr": round(iqr, 4),
        "lower_fence": round(lower_fence, 4),
        "upper_fence": round(upper_fence, 4),
        "method": "iqr",
        "factor": factor,
    }


def detect_outliers_zscore(values: list[float], threshold: float = 3.0) -> dict:
    """Detect outliers using z-score method.

    Returns dict with outlier indices/values.
    """
    if len(values) < 3:
        return {
            "n_outliers": 0,
            "outlier_indices": [],
            "outlier_values": [],
            "method": "zscore",
        }

    n = len(values)
    mean = sum(values) / n
    std = math.sqrt(sum((v - mean) ** 2 for v in values) / (n - 1))
    if std < 1e-10:
        return {
            "n_outliers": 0,
            "outlier_indices": [],
            "outlier_values": [],
            "mean": round(mean, 4),
            "std": 0.0,
            "method": "zscore",
        }

    outlier_indices = []
    outlier_values = []
    for i, v in enumerate(values):
        z = abs(v - mean) / std
        if z > threshold:
            outlier_indices.append(i)
            outlier_values.append(v)

    return {
        "n_outliers": len(outlier_indices),
        "outlier_indices": outlier_indices,
        "outlier_values": [round(v, 4) for v in outlier_values],
        "mean": round(mean, 4),
        "std": round(std, 4),
        "threshold": threshold,
        "method": "zscore",
    }


def detect_source_outliers(
    data: dict,
    label: str,
    method: str = "iqr",
    iqr_factor: float = 1.5,
    zscore_threshold: float = 3.0,
) -> dict:
    """Run outlier detection on a source TR's group_stats scores.

    Returns summary with per-task outlier counts and flagged groups.
    """
    gs = data.get("group_stats", {})
    if not gs:
        return {"label": label, "n_groups": 0, "n_outliers_total": 0, "per_task": {}}

    # Group scores by task
    task_scores: dict[str, list[tuple[str, float]]] = {}
    for key, val in gs.items():
        if not isinstance(val, dict):
            continue
        score = val.get("mean_score") or val.get("score_mean")
        if score is None:
            continue
        # Extract task from key (varies by TR format)
        parts = key.split("|") if "|" in key else key.split("__")
        task = None
        for p in parts:
            if p in SAFETY_TASKS or p in CAPABILITY_TASKS:
                task = p
                break
        if task:
            task_scores.setdefault(task, []).append((key, score))

    per_task: dict[str, dict] = {}
    total_outliers = 0
    flagged_groups: list[str] = []

    for task, scored_keys in task_scores.items():
        values = [s for _, s in scored_keys]
        if method == "zscore":
            result = detect_outliers_zscore(values, zscore_threshold)
        else:
            result = detect_outliers_iqr(values, iqr_factor)

        outlier_keys = [scored_keys[i][0] for i in result["outlier_indices"]]
        per_task[task] = {
            "n_values": len(values),
            "n_outliers": result["n_outliers"],
            "outlier_keys": outlier_keys,
        }
        total_outliers += result["n_outliers"]
        flagged_groups.extend(outlier_keys)

    return {
        "label": label,
        "method": method,
        "n_groups": len(gs),
        "n_tasks_checked": len(per_task),
        "n_outliers_total": total_outliers,
        "flagged_groups": flagged_groups,
        "per_task": per_task,
    }


# ---------------------------------------------------------------------------
# Config loader
# ---------------------------------------------------------------------------


def load_config(config_path: Path | None = None) -> dict:
    """Load TR137 config.yaml, returning defaults if not found."""
    if config_path is None:
        config_path = _REPO_ROOT / "research" / "tr137" / "config.yaml"
    if not config_path.exists():
        logger.warning("Config not found: %s — using defaults", config_path)
        return {}
    try:
        import yaml  # type: ignore

        with open(config_path, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except ImportError:
        # Fallback: parse simple YAML manually is fragile; just warn
        logger.warning("PyYAML not available — using default config")
        return {}
    except Exception as e:
        logger.error("Failed to load config %s: %s", config_path, e)
        return {}


__all__ = [
    "SHARED_MODELS",
    "ANCHOR_QUANT",
    "ANCHOR_N",
    "ANCHOR_BACKEND",
    "SAFETY_TASKS",
    "CAPABILITY_TASKS",
    "ALL_TASKS",
    "TASK_METRIC",
    "QUANT_BPW",
    "BASELINE_TOLERANCE_PP",
    "RISK_THRESHOLDS",
    "TR134_MODELS",
    "TR135_MODELS",
    "TR136_MODELS",
    "TR134_REQUIRED_KEYS",
    "TR135_REQUIRED_KEYS",
    "TR136_REQUIRED_KEYS",
    "FAMILY_PREFIXES",
    "infer_family",
    "classify_risk",
    "validate_analysis",
    "validate_source_status",
    "check_source_completeness",
    "detect_outliers_iqr",
    "detect_outliers_zscore",
    "detect_source_outliers",
    "load_tr134",
    "load_tr135",
    "load_tr136",
    "load_config",
    "find_latest_run",
]
