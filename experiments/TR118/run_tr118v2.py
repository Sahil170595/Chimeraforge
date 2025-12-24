#!/usr/bin/env python3
"""
TR118v2: Tiny vs 124M (gpt2) data-gathering orchestrator.

This runner generates two isolated TR118 configs (tiny + gpt2) with unique
`output.results_dir` per run, then executes the existing TR118 pipeline via
`scripts/tr118/run_experiment.py`.

Why this exists:
- TR118 writes some processed artifacts to fixed filenames (e.g.
  `latency_summary_<mode>.csv`, `perplexity_results.csv`). Reusing a single
  results_dir would overwrite data across runs.
- TR118v2 needs apples-to-apples runs across two models.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import subprocess
import sys
import time
from typing import Any

import yaml

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.tr118.artifact_utils import resolve_repo_path


def _load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = dict(base)
    for key, val in override.items():
        if isinstance(val, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], val)  # type: ignore[arg-type]
        else:
            out[key] = val
    return out


def _sanitize_component(s: str) -> str:
    s = (s or "").strip()
    if not s:
        return ""
    s = re.sub(r"[^A-Za-z0-9._-]+", "-", s)
    s = re.sub(r"-{2,}", "-", s).strip("-")
    return s


def _model_tag(model_name_or_path: str) -> str:
    try:
        return Path(model_name_or_path).name
    except Exception:
        return _sanitize_component(model_name_or_path) or "model"


def _git_sha() -> str | None:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True, cwd=str(_REPO_ROOT)).strip() or None
    except Exception:
        return None


def _latest_file(paths: list[Path]) -> Path | None:
    existing = [p for p in paths if p.exists()]
    if not existing:
        return None
    return sorted(existing, key=lambda p: p.stat().st_mtime)[-1]


def _make_int8_cache_path(
    artifacts_root: Path,
    model_name_or_path: str,
    int8_cfg: dict[str, Any],
) -> Path:
    tag = _model_tag(model_name_or_path)
    calib_dir = artifacts_root / tag / "calib"
    ds = str(int8_cfg.get("dataset_config", "wikitext-2-raw-v1")).replace("/", "_")
    split = str(int8_cfg.get("split", "test")).replace("/", "_")
    samples = int(int8_cfg.get("samples", 256) or 256)
    batch = int(int8_cfg.get("batch_size", 8) or 8)
    seq = int(int8_cfg.get("seq_len", 128) or 128)
    return calib_dir / f"{tag}_{ds}_{split}_{samples}x{batch}x{seq}.calib"


def main() -> int:
    parser = argparse.ArgumentParser(description="TR118v2 runner (tiny vs gpt2)")
    parser.add_argument(
        "--base-config",
        default="scripts/tr118/configs/matrix_postdoc.yaml",
        help="Base TR118 config yaml (used as a template for both models)",
    )
    parser.add_argument(
        "--results-root",
        default="scripts/tr118/results/tr118v2",
        help="Root directory for TR118v2 run bundles",
    )
    parser.add_argument(
        "--artifacts-root",
        default="artifacts/tr118v2",
        help="Root directory for TR118v2 ONNX/TRT artifacts (per model)",
    )
    parser.add_argument(
        "--label",
        default="",
        help="Optional label appended to the run folder name (e.g. 'e2e', 'driver566')",
    )
    parser.add_argument("--device", default="cuda", help="Device for PyTorch perplexity baseline (cpu/cuda)")
    parser.add_argument(
        "--models",
        nargs="*",
        choices=["tiny", "gpt2"],
        default=None,
        help="Which model runs to execute (default: both)",
    )
    parser.add_argument("--tiny-model", default="models/tiny-gpt2", help="Tiny model name/path (repo-local by default)")
    parser.add_argument("--gpt2-model", default="gpt2", help="124M model name/path")
    parser.add_argument(
        "--prompt-config",
        default=None,
        help="Override prompt config yaml (defaults to config.benchmark.prompt_config_path)",
    )
    parser.add_argument(
        "--modes",
        nargs="*",
        choices=["prefill", "generate"],
        default=None,
        help="Modes to run (defaults to config.benchmark.modes)",
    )
    parser.add_argument("--skip-accuracy", action="store_true", help="Skip perplexity validation")
    parser.add_argument("--with-plots", action="store_true", help="Generate plots")
    parser.add_argument("--with-report", action="store_true", help="Generate per-run TR118 reports into each run folder")
    parser.add_argument("--force-export", action="store_true", help="Force ONNX re-export for the first mode")
    parser.add_argument("--force-trt-rebuild", action="store_true", help="Force TRT rebuild for the first mode")
    args = parser.parse_args()

    base_cfg_path = resolve_repo_path(_REPO_ROOT, str(args.base_config))
    base_cfg = _load_yaml(base_cfg_path)

    results_root = resolve_repo_path(_REPO_ROOT, str(args.results_root))
    artifacts_root = resolve_repo_path(_REPO_ROOT, str(args.artifacts_root))

    started = time.time()
    stamp = time.strftime("%Y%m%d_%H%M%S", time.localtime(started))
    label = _sanitize_component(str(args.label))
    run_slug = f"{stamp}_{label}" if label else stamp

    wanted = args.models or ["tiny", "gpt2"]
    model_runs: list[tuple[str, str, str]] = []
    if "tiny" in wanted:
        model_runs.append(("tiny", str(args.tiny_model), "Tiny/toy model run"))
    if "gpt2" in wanted:
        model_runs.append(("gpt2", str(args.gpt2_model), "GPT-2 (124M) run"))

    tr118v2_runs: list[dict[str, Any]] = []
    any_failed = False

    for key, model_name, desc in model_runs:
        tag = _model_tag(model_name)
        run_dir = results_root / run_slug / tag
        proc_dir = run_dir / "processed"
        proc_dir.mkdir(parents=True, exist_ok=True)

        # Build a generated config for this model with isolated results_dir and
        # per-model ONNX/TRT artifact dirs.
        override: dict[str, Any] = {
            "model": {"name": model_name, "description": desc},
            "output": {
                "results_dir": str(run_dir.as_posix()),
                "onnx_dir": str((artifacts_root / tag / "onnx").as_posix()),
                "tensorrt_dir": str((artifacts_root / tag / "tensorrt").as_posix()),
            },
        }

        # Ensure INT8 cache path is model-specific (avoid collisions and ambiguity).
        trt_cfg = base_cfg.get("tensorrt") if isinstance(base_cfg.get("tensorrt"), dict) else {}
        int8_cfg = trt_cfg.get("int8_calibration") if isinstance(trt_cfg.get("int8_calibration"), dict) else None
        if int8_cfg is not None:
            int8_cfg = dict(int8_cfg)
            int8_cfg["cache_path"] = str(_make_int8_cache_path(artifacts_root, model_name, int8_cfg).as_posix())
            override.setdefault("tensorrt", {})["int8_calibration"] = int8_cfg  # type: ignore[index]

        merged = _deep_merge(base_cfg, override)
        gen_cfg_path = proc_dir / f"config_generated_tr118v2_{key}.yaml"
        gen_cfg_path.write_text(yaml.safe_dump(merged, sort_keys=False), encoding="utf-8")

        cmd = [
            sys.executable,
            "scripts/tr118/run_experiment.py",
            "--config",
            str(gen_cfg_path),
            "--device",
            str(args.device),
        ]
        if args.modes:
            cmd += ["--modes", *[str(m) for m in args.modes]]
        if args.prompt_config:
            cmd += ["--prompt-config", str(args.prompt_config)]
        if not args.with_plots:
            cmd.append("--no-plots")
        if not args.with_report:
            cmd.append("--no-report")
        else:
            cmd += ["--report-out", str(proc_dir / f"Technical_Report_118_{tag}.md")]
        if args.skip_accuracy:
            cmd.append("--skip-accuracy")
        if args.force_export:
            cmd.append("--force-export")
        if args.force_trt_rebuild:
            cmd.append("--force-trt-rebuild")

        success = True
        error: str | None = None
        try:
            subprocess.run(cmd, check=True, cwd=str(_REPO_ROOT))
        except subprocess.CalledProcessError as exc:
            success = False
            error = f"{type(exc).__name__}: {exc}"
            any_failed = True
            print(f"WARNING: TR118v2 run failed for {tag}: {error}")

        manifest = _latest_file(list(proc_dir.glob("experiment_manifest_*.json"))) if success else None
        tr118v2_runs.append(
            {
                "key": key,
                "model": model_name,
                "model_tag": tag,
                "success": success,
                "error": error,
                "generated_config_path": str(gen_cfg_path),
                "results_dir": str(run_dir),
                "manifest_path": str(manifest) if manifest else None,
            }
        )

    ended = time.time()
    out_path = results_root / run_slug / "tr118v2_run_manifest.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(
            {
                "tr": "TR118v2",
                "started_at": started,
                "ended_at": ended,
                "duration_s": ended - started,
                "run_slug": run_slug,
                "git_sha": _git_sha(),
                "base_config_path": str(base_cfg_path),
                "device": str(args.device),
                "results_root": str(results_root),
                "artifacts_root": str(artifacts_root),
                "runs": tr118v2_runs,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"Wrote TR118v2 run manifest to {out_path}")
    return 1 if any_failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
