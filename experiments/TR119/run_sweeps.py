#!/usr/bin/env python3
"""
TR119 sweep runner.

Runs multiple TR119 experiments from a base config + per-variant overrides.

Design goals:
- Tests first: runs `run_experiment.py` with `--no-report` by default.
- Artifact-driven: writes a sweep manifest that records each variant's
  generated config + experiment manifest path for later report generation.
- Safe isolation: defaults each variant to its own results directories to avoid clobbering.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
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


def _apply_default_isolation(cfg: dict[str, Any], variant_name: str) -> dict[str, Any]:
    out_cfg = dict(cfg)
    output = out_cfg.get("output") if isinstance(out_cfg.get("output"), dict) else {}
    output = dict(output)
    # Always isolate results per variant to avoid clobbering.
    output["results_dir"] = f"scripts/tr119/results/sweeps/{variant_name}"
    out_cfg["output"] = output
    return out_cfg


def _latest_file(paths: list[Path]) -> Path | None:
    existing = [p for p in paths if p.exists()]
    if not existing:
        return None
    return sorted(existing, key=lambda p: p.stat().st_mtime)[-1]


def main() -> int:
    parser = argparse.ArgumentParser(description="TR119 sweep runner")
    parser.add_argument(
        "--base-config",
        default="scripts/tr119/configs/baseline.yaml",
        help="Base TR119 config yaml",
    )
    parser.add_argument(
        "--variants-dir",
        default="scripts/tr119/configs/variants",
        help="Directory of variant override yamls",
    )
    parser.add_argument(
        "--variants",
        nargs="*",
        default=None,
        help="Variant names (file stems) to run (defaults to all yamls under variants-dir)",
    )
    parser.add_argument(
        "--skip-baseline",
        action="store_true",
        help="Skip running the base config as the 'baseline' variant.",
    )
    parser.add_argument(
        "--device",
        default="cuda",
        help="Device for benchmarks (passed to run_experiment.py)",
    )
    parser.add_argument(
        "--with-report",
        action="store_true",
        help="Generate reports for each variant (default: --no-report)",
    )
    parser.add_argument(
        "--with-plots",
        action="store_true",
        help="Generate plots for each variant (default: --no-plots)",
    )
    args = parser.parse_args()

    base_cfg_path = resolve_repo_path(_REPO_ROOT, str(args.base_config))
    base_cfg = _load_yaml(base_cfg_path)
    variants_dir = resolve_repo_path(_REPO_ROOT, str(args.variants_dir))

    variants_to_run: list[tuple[str, Path]] = []
    if not args.skip_baseline:
        variants_to_run.append(("baseline", base_cfg_path))

    if variants_dir.exists() and variants_dir.is_dir():
        variant_files = sorted(variants_dir.glob("*.yaml"))
        if args.variants:
            variant_files = [f for f in variant_files if f.stem in args.variants]
        for vf in variant_files:
            variants_to_run.append((vf.stem, vf))

    if not variants_to_run:
        print("No variants to run")
        return 1

    sweep_started = time.time()
    sweep_id = int(sweep_started)
    sweep_manifest: dict[str, Any] = {
        "tr": "TR119",
        "sweep_id": sweep_id,
        "started_at": sweep_started,
        "base_config_path": str(base_cfg_path),
        "variants": [],
    }

    for variant_name, variant_path in variants_to_run:
        print(f"\n{'='*60}")
        print(f"Running TR119 variant: {variant_name}")
        print(f"{'='*60}\n")

        variant_cfg = _load_yaml(variant_path)
        merged_cfg = _deep_merge(base_cfg, variant_cfg)
        merged_cfg = _apply_default_isolation(merged_cfg, variant_name)

        # Write merged config to a temp location
        results_root = resolve_repo_path(_REPO_ROOT, str(merged_cfg["output"]["results_dir"]))
        processed_dir = results_root / "processed"
        processed_dir.mkdir(parents=True, exist_ok=True)
        merged_cfg_path = processed_dir / f"merged_config_{variant_name}_{sweep_id}.yaml"
        merged_cfg_path.write_text(yaml.dump(merged_cfg, default_flow_style=False), encoding="utf-8")

        variant_started = time.time()
        cmd = [
            sys.executable,
            "scripts/tr119/run_experiment.py",
            "--config",
            str(merged_cfg_path),
            "--device",
            str(args.device),
        ]
        if not args.with_report:
            cmd.append("--no-report")
        if not args.with_plots:
            cmd.append("--no-plots")

        try:
            subprocess.run(cmd, check=True, cwd=str(_REPO_ROOT))
            variant_ended = time.time()

            # Find the experiment manifest
            manifests = sorted(processed_dir.glob("experiment_manifest_*.json"), key=lambda p: p.stat().st_mtime)
            manifest_path = manifests[-1] if manifests else None

            variant_entry: dict[str, Any] = {
                "variant_name": variant_name,
                "variant_config_path": str(variant_path),
                "merged_config_path": str(merged_cfg_path),
                "started_at": variant_started,
                "ended_at": variant_ended,
                "duration_s": variant_ended - variant_started,
                "experiment_manifest_path": str(manifest_path) if manifest_path else None,
                "status": "completed",
            }
        except subprocess.CalledProcessError as exc:
            variant_ended = time.time()
            variant_entry = {
                "variant_name": variant_name,
                "variant_config_path": str(variant_path),
                "merged_config_path": str(merged_cfg_path),
                "started_at": variant_started,
                "ended_at": variant_ended,
                "duration_s": variant_ended - variant_started,
                "status": "failed",
                "error": str(exc),
            }
        sweep_manifest["variants"].append(variant_entry)

    sweep_ended = time.time()
    sweep_manifest["ended_at"] = sweep_ended
    sweep_manifest["duration_s"] = sweep_ended - sweep_started

    # Write sweep manifest
    sweep_results_root = resolve_repo_path(_REPO_ROOT, "scripts/tr119/results/sweeps")
    sweep_results_root.mkdir(parents=True, exist_ok=True)
    manifest_path = sweep_results_root / f"sweep_manifest_{sweep_id}.json"
    manifest_path.write_text(json.dumps(sweep_manifest, indent=2), encoding="utf-8")
    print(f"\nTR119 sweep manifest written to {manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

