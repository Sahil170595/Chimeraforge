#!/usr/bin/env python3
"""
Re-fit the ONNX CPU vs PyTorch crossover curve using available model data.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml


def _latest(glob: list[Path]) -> Path | None:
    files = [p for p in glob if p.exists()]
    if not files:
        return None
    return sorted(files, key=lambda p: p.stat().st_mtime)[-1]


def _load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _load_model_config(model_ref: str, repo_root: Path) -> dict[str, Any] | None:
    path = Path(model_ref)
    if not path.exists() and not path.is_absolute():
        alt = repo_root / model_ref
        if alt.exists():
            path = alt
        else:
            alt = repo_root / "scripts" / "tr118" / model_ref
            if alt.exists():
                path = alt
    if path.exists():
        cfg_path = path / "config.json"
        if cfg_path.exists():
            return json.loads(cfg_path.read_text(encoding="utf-8"))
    try:
        from transformers import AutoConfig  # type: ignore

        cfg = AutoConfig.from_pretrained(model_ref, local_files_only=True)
        return cfg.to_dict()
    except Exception:
        return None


def _count_gpt2_params(cfg: dict[str, Any]) -> int:
    n_embd = int(cfg["n_embd"])
    n_layer = int(cfg["n_layer"])
    vocab_size = int(cfg["vocab_size"])
    n_positions = int(cfg.get("n_positions") or cfg.get("n_ctx") or 1024)
    n_inner = int(cfg.get("n_inner") or 4 * n_embd)

    total = vocab_size * n_embd + n_positions * n_embd
    attn_w = 4 * n_embd * n_embd
    attn_b = 4 * n_embd
    mlp_w = 2 * n_embd * n_inner
    mlp_b = n_inner + n_embd
    ln = 4 * n_embd
    per_layer = attn_w + attn_b + mlp_w + mlp_b + ln
    total += n_layer * per_layer
    total += 2 * n_embd
    return int(total)


def _load_param_count(processed_dir: Path, repo_root: Path) -> tuple[int | None, str | None]:
    cfg_path = _latest(list(processed_dir.glob("config_used_*.yaml")))
    if cfg_path is None:
        return None, None
    cfg = _load_yaml(cfg_path)
    model_ref = str(cfg.get("model", {}).get("name", "")).strip()
    if not model_ref:
        return None, None
    model_cfg = _load_model_config(model_ref, repo_root)
    if model_cfg is None:
        # Fallback to ONNX initializer count if present
        export_meta = _latest(list(processed_dir.glob("export_metadata_*.json")))
        if export_meta and export_meta.exists():
            meta = json.loads(export_meta.read_text(encoding="utf-8"))
            onnx_inspect = meta.get("onnx_inspect", {}) if isinstance(meta, dict) else {}
            init_numel = onnx_inspect.get("initializer_numel")
            if isinstance(init_numel, int):
                return init_numel, model_ref
        if model_ref.lower() == "gpt2":
            model_cfg = {
                "n_embd": 768,
                "n_layer": 12,
                "n_inner": 3072,
                "n_positions": 1024,
                "vocab_size": 50257,
            }
        else:
            return None, model_ref
    return _count_gpt2_params(model_cfg), model_ref


def _load_throughput(processed_dir: Path, backend: str) -> float | None:
    lat_path = processed_dir / "latency_summary_prefill.csv"
    if not lat_path.exists():
        return None
    df = pd.read_csv(lat_path)
    if "degraded_rate" in df.columns:
        df = df[df["degraded_rate"] < 1.0]
    agg = df.groupby("backend")["throughput_mean_tok_s"].mean()
    if backend not in agg:
        return None
    return float(agg[backend])


def _fit_power_law(params: list[float], ratios: list[float], n_boot: int) -> dict[str, Any]:
    x = np.log(np.array(params))
    y = np.log(np.array(ratios))
    slope, intercept = np.polyfit(x, y, 1)

    def _crossover(a: float, b: float) -> float:
        return math.exp(-b / a) if a != 0 else float("nan")

    crossover = _crossover(slope, intercept)

    boot = []
    rng = np.random.default_rng(42)
    for _ in range(n_boot):
        idx = rng.integers(0, len(x), len(x))
        xb = x[idx]
        yb = y[idx]
        s, i = np.polyfit(xb, yb, 1)
        boot.append(_crossover(s, i))
    boot = [b for b in boot if math.isfinite(b)]
    boot.sort()
    if boot:
        lo = boot[int(0.025 * len(boot))]
        hi = boot[int(0.975 * len(boot)) - 1]
    else:
        lo = hi = float("nan")

    return {
        "slope_k": slope,
        "intercept_logA0": intercept,
        "crossover_params": crossover,
        "crossover_ci_95": [lo, hi],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify crossover power-law fit")
    parser.add_argument(
        "--output",
        default="scripts/tr118/results/tr118v2_audit/crossover_fit.json",
        help="Output JSON path",
    )
    parser.add_argument(
        "--bootstrap",
        type=int,
        default=2000,
        help="Bootstrap iterations for CI",
    )
    args = parser.parse_args()

    candidates = [
        Path("scripts/tr118/results/tr118v2/20251213_135135_deep/tiny-gpt2/processed"),
        Path("scripts/tr118/results/tr118v2/20251213_153314_gpt2_11m/gpt2-1m/processed"),
        Path("scripts/tr118/results/validation_45m/processed"),
        Path("scripts/tr118/results/tr118v2_crossover/gpt2-5m/processed"),
        Path("scripts/tr118/results/tr118v2_crossover/gpt2-25m/processed"),
        Path("scripts/tr118/results/tr118v2_crossover/gpt2-50m/processed"),
        Path("scripts/tr118/results/tr118v2_crossover/gpt2-75m/processed"),
        Path("scripts/tr118/results/tr118v2_crossover/gpt2-100m/processed"),
        Path("scripts/tr118/results/tr118v2/20251213_135135_deep/gpt2/processed"),
    ]

    data_points: list[dict[str, Any]] = []
    repo_root = Path(__file__).resolve().parents[2]
    for processed_dir in candidates:
        if not processed_dir.exists():
            continue
        params, model_ref = _load_param_count(processed_dir, repo_root)
        if params is None:
            continue
        onnx_cpu = _load_throughput(processed_dir, "onnxruntime-cpu")
        pytorch = _load_throughput(processed_dir, "transformers-gpu-compile")
        if onnx_cpu is None or pytorch is None:
            continue
        ratio = onnx_cpu / pytorch if pytorch > 0 else None
        data_points.append(
            {
                "processed_dir": str(processed_dir),
                "model_ref": model_ref,
                "parameter_count": params,
                "onnx_cpu_tput": onnx_cpu,
                "pytorch_tput": pytorch,
                "ratio": ratio,
            }
        )

    data_points.sort(key=lambda r: r["parameter_count"])
    params = [float(r["parameter_count"]) for r in data_points]
    ratios = [float(r["ratio"]) for r in data_points if r.get("ratio") is not None]

    if len(params) < 3:
        raise SystemExit("Not enough data points to fit power-law")

    fit = _fit_power_law(params, ratios, args.bootstrap)
    report = {
        "points": data_points,
        "fit": fit,
    }

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Wrote crossover fit to {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
