#!/usr/bin/env python3
"""
Verify tiny model specs (vocab size, param count) and perplexity interpretation.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from typing import Any

import yaml


def _load_config(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _latest(glob: list[Path]) -> Path | None:
    files = [p for p in glob if p.exists()]
    if not files:
        return None
    return sorted(files, key=lambda p: p.stat().st_mtime)[-1]


def _load_model_config(model_ref: str) -> dict[str, Any] | None:
    path = Path(model_ref)
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


def _load_perplexity(path: Path, baseline_backend: str) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("backend") == baseline_backend:
                mean_nll = float(row.get("mean_nll") or 0.0)
                ppl = float(row.get("perplexity") or 0.0)
                return {
                    "backend": baseline_backend,
                    "mean_nll": mean_nll,
                    "perplexity": ppl,
                }
    return {}


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify tiny model vocab + perplexity")
    parser.add_argument(
        "--processed-dir",
        default="scripts/tr118/results/tr118v2/20251213_135135_deep/tiny-gpt2/processed",
        help="Processed directory for tiny-gpt2 run",
    )
    parser.add_argument(
        "--baseline-backend",
        default="transformers-gpu-compile",
        help="Backend to use for perplexity baseline",
    )
    parser.add_argument(
        "--output",
        default="scripts/tr118/results/tr118v2_audit/tiny_model_check.json",
        help="Output JSON path",
    )
    args = parser.parse_args()

    processed_dir = Path(args.processed_dir)
    cfg_path = _latest(list(processed_dir.glob("config_used_*.yaml")))
    if cfg_path is None:
        raise SystemExit(f"No config_used_*.yaml found under {processed_dir}")
    cfg = _load_config(cfg_path)
    model_ref = str(cfg.get("model", {}).get("name", "")).strip()
    if not model_ref:
        raise SystemExit("Model name missing from config")

    model_cfg = _load_model_config(model_ref)
    if model_cfg is None:
        raise SystemExit(f"Unable to load model config for {model_ref}")

    vocab_size = int(model_cfg.get("vocab_size", 0))
    param_count = _count_gpt2_params(model_cfg)

    ppl_path = processed_dir / "perplexity_results.csv"
    ppl_data = _load_perplexity(ppl_path, args.baseline_backend)
    mean_nll = float(ppl_data.get("mean_nll", 0.0))
    ppl_from_nll = math.exp(mean_nll) if mean_nll > 0 else None

    report = {
        "model_ref": model_ref,
        "vocab_size": vocab_size,
        "parameter_count": param_count,
        "perplexity_baseline": ppl_data,
        "perplexity_from_mean_nll": ppl_from_nll,
        "uniform_perplexity": vocab_size,
        "ratio_vs_uniform": (ppl_from_nll / vocab_size) if ppl_from_nll and vocab_size else None,
    }

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Wrote tiny model audit to {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
