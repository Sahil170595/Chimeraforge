#!/usr/bin/env python3
"""
TR118 sweep runner.

Runs multiple TR118 experiments from a base config + per-variant overrides.

Design goals:
- Tests first: runs `run_experiment.py` with `--no-report` by default.
- Artifact-driven: writes a sweep manifest that records each variant's
  generated config + experiment manifest path for later report generation.
- Safe isolation: defaults each variant to its own results + ONNX/TRT artifact
  directories to avoid clobbering other runs.
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
    # Always isolate results + TRT engines per variant to avoid clobbering.
    output["results_dir"] = f"scripts/tr118/results/sweeps/{variant_name}"
    output["tensorrt_dir"] = f"artifacts/tr118/sweeps/{variant_name}/tensorrt"
    # Prefer reusing a pre-exported ONNX (export can be flaky on some Windows+torch builds).
    if not str(output.get("onnx_dir", "")).strip():
        output["onnx_dir"] = "artifacts/onnx"
    out_cfg["output"] = output
    return out_cfg


def _latest_file(paths: list[Path]) -> Path | None:
    existing = [p for p in paths if p.exists()]
    if not existing:
        return None
    return sorted(existing, key=lambda p: p.stat().st_mtime)[-1]


def main() -> int:
    parser = argparse.ArgumentParser(description="TR118 sweep runner")
    parser.add_argument(
        "--base-config",
        default="scripts/tr118/configs/sweep_base.yaml",
        help="Base TR118 config yaml",
    )
    parser.add_argument(
        "--variants-dir",
        default="scripts/tr118/configs/variants",
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
        help="Device for perplexity baseline (passed to run_experiment.py)",
    )
    parser.add_argument(
        "--with-accuracy",
        action="store_true",
        help="Run perplexity validation (default: skip for faster sweeps).",
    )
    parser.add_argument(
        "--with-plots",
        action="store_true",
        help="Generate plots (default: off).",
    )
    parser.add_argument(
        "--with-report",
        action="store_true",
        help="Generate per-variant reports (default: off).",
    )
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
    args = parser.parse_args()

    base_cfg_path = resolve_repo_path(_REPO_ROOT, str(args.base_config))
    base_cfg = _load_yaml(base_cfg_path)
    variants_dir = resolve_repo_path(_REPO_ROOT, str(args.variants_dir))
    variants_dir.mkdir(parents=True, exist_ok=True)

    variant_paths = sorted(variants_dir.glob("*.yaml"))
    if args.variants:
        selected = {str(v).strip() for v in args.variants if str(v).strip()}
        variant_paths = [p for p in variant_paths if p.stem in selected]

    sweep_started = time.time()
    sweep_runs: list[dict[str, Any]] = []

    def _run_variant(name: str, override: dict[str, Any]) -> None:
        merged = _deep_merge(base_cfg, override)
        merged = _apply_default_isolation(merged, name)

        results_dir = resolve_repo_path(_REPO_ROOT, str(merged.get("output", {}).get("results_dir", "")))
        processed_dir = results_dir / "processed"
        processed_dir.mkdir(parents=True, exist_ok=True)

        gen_cfg_path = processed_dir / f"config_generated_{name}.yaml"
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
            cmd += ["--report-out", str(processed_dir / f"Technical_Report_118_{name}.md")]
        if not args.with_accuracy:
            cmd.append("--skip-accuracy")

        subprocess.run(cmd, check=True, cwd=str(_REPO_ROOT))

        manifest = _latest_file(list(processed_dir.glob("experiment_manifest_*.json")))
        sweep_runs.append(
            {
                "variant": name,
                "generated_config_path": str(gen_cfg_path),
                "results_dir": str(results_dir),
                "manifest_path": str(manifest) if manifest else None,
            }
        )

    if not args.skip_baseline:
        _run_variant("baseline", override={})

    for vpath in variant_paths:
        _run_variant(vpath.stem, _load_yaml(vpath))

    sweep_ended = time.time()
    out_root = resolve_repo_path(_REPO_ROOT, "scripts/tr118/results/sweeps")
    out_root.mkdir(parents=True, exist_ok=True)
    out_path = out_root / f"sweep_manifest_{int(sweep_started)}.json"
    out_path.write_text(
        json.dumps(
            {
                "tr": "TR118",
                "sweep_started_at": sweep_started,
                "sweep_ended_at": sweep_ended,
                "duration_s": sweep_ended - sweep_started,
                "base_config_path": str(base_cfg_path),
                "variants_dir": str(variants_dir),
                "variants": sweep_runs,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"Wrote sweep manifest to {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
