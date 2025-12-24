#!/usr/bin/env python3
"""
TR119: End-to-end cost & energy experiment orchestrator.

Patterned after TR118's `run_experiment.py`, but focused on:
  1) Running latency/throughput benchmarks on selected backends
  2) Capturing resource telemetry (power, temperature, utilization)
  3) Converting telemetry into cost/energy/TCO metrics
  4) Generating plots and a publish-ready TR119 report

Artifacts are written under `scripts/tr119/results/` as configured.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time
from typing import Any

import yaml

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.tr118.artifact_utils import resolve_repo_path  # reuse helper


def _load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _try_version(module_name: str) -> str | None:
    try:
        mod = __import__(module_name)
    except Exception:
        return None
    return str(getattr(mod, "__version__", None) or getattr(mod, "version", None) or None)


def _torch_cuda_device_info() -> dict[str, Any] | None:
    try:
        import torch  # type: ignore

        if not torch.cuda.is_available():
            return None
        idx = int(torch.cuda.current_device())
        props = torch.cuda.get_device_properties(idx)
        return {
            "index": idx,
            "name": str(torch.cuda.get_device_name(idx)),
            "capability": f"{props.major}.{props.minor}",
            "total_memory_mb": float(props.total_memory / (1024**2)),
        }
    except Exception:
        return None


def _onnxruntime_available_providers() -> list[str] | None:
    try:
        import onnxruntime as ort  # type: ignore

        return [str(p) for p in ort.get_available_providers()]
    except Exception:
        return None


def _run(cmd: list[str], env: dict[str, str] | None = None) -> None:
    subprocess.run(cmd, check=True, env=env, cwd=str(_REPO_ROOT))


def _git_sha() -> str | None:
    try:
        out = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
        return out or None
    except Exception:
        return None


def main() -> int:
    parser = argparse.ArgumentParser(description="TR119 end-to-end runner")
    parser.add_argument(
        "--config",
        default="scripts/tr119/configs/baseline.yaml",
        help="TR119 config yaml",
    )
    parser.add_argument(
        "--device",
        default="cuda",
        help="Device for benchmarks (cpu/cuda)",
    )
    parser.add_argument(
        "--prompt-config",
        default=None,
        help="Prompt config yaml (defaults to env or config)",
    )
    parser.add_argument(
        "--mode",
        choices=["prefill", "generate"],
        default=None,
        help="Benchmark mode override (defaults to config)",
    )
    parser.add_argument(
        "--no-plots",
        action="store_true",
        help="Skip visualization step",
    )
    parser.add_argument(
        "--no-report",
        action="store_true",
        help="Skip report generation step",
    )
    parser.add_argument(
        "--report-out",
        default="reports/generated/Technical_Report_119.md",
        help="Where to write the TR119 report",
    )
    parser.add_argument(
        "--skip-validation",
        action="store_true",
        help="Skip cost/energy validation step",
    )
    parser.add_argument(
        "--skip-deep-analysis",
        action="store_true",
        help="Skip cost/energy deep analysis step",
    )
    args = parser.parse_args()

    cfg_path = resolve_repo_path(_REPO_ROOT, str(args.config))
    cfg = _load_yaml(cfg_path)
    results_dir = resolve_repo_path(_REPO_ROOT, str(cfg["output"]["results_dir"]))
    processed_dir = results_dir / "processed"
    processed_dir.mkdir(parents=True, exist_ok=True)
    prompt_cfg_value = (
        args.prompt_config
        or os.getenv("BANTER_TR119_PROMPT_CONFIG")
        or cfg.get("benchmark", {}).get("prompt_config_path")
        or cfg.get("prompt_config_path")
        or "scripts/tr117/configs/matrix_tier3.yaml"
    )
    prompt_cfg_path = resolve_repo_path(_REPO_ROOT, str(prompt_cfg_value))

    started = time.time()
    run_id = int(started)
    manifest: dict[str, Any] = {
        "tr": "TR119",
        "started_at": started,
        "run_id": run_id,
        "config_path": str(cfg_path),
        "prompt_config_path": str(prompt_cfg_path),
        "git_sha": _git_sha(),
        "platform": {
            "python": sys.version.replace("\n", " "),
            "os": platform.platform(),
            "machine": platform.machine(),
            "cuda_device": _torch_cuda_device_info(),
            "onnxruntime_providers": _onnxruntime_available_providers(),
        },
        "package_versions": {
            "torch": _try_version("torch"),
            "transformers": _try_version("transformers"),
            "onnx": _try_version("onnx"),
            "onnxruntime": _try_version("onnxruntime"),
            "tensorrt": _try_version("tensorrt"),
            "numpy": _try_version("numpy"),
            "pandas": _try_version("pandas"),
            "scipy": _try_version("scipy"),
        },
    }

    cfg_snapshot_path = processed_dir / f"config_used_{int(started)}.yaml"
    cfg_snapshot_path.write_text(cfg_path.read_text(encoding="utf-8"), encoding="utf-8")
    manifest["config_snapshot_path"] = str(cfg_snapshot_path)

    # 1) Benchmark with resource telemetry
    bench_cmd = [
        sys.executable,
        "scripts/tr119/run_benchmark.py",
        "--config",
        str(cfg_path),
        "--prompt-config",
        str(prompt_cfg_path),
        "--device",
        str(args.device),
        "--run-id",
        str(run_id),
    ]
    if args.mode:
        bench_cmd += ["--mode", str(args.mode)]
    _run(bench_cmd)

    # 2) Analyze results into latency/throughput + energy/cost summaries
    _run(
        [
            sys.executable,
            "scripts/tr119/analyze_results.py",
            "--config",
            str(cfg_path),
        ]
    )
    manifest["latency_summary_path"] = str(processed_dir / "latency_summary_cost.csv")
    manifest["cost_energy_summary_path"] = str(processed_dir / "cost_energy_summary.json")
    
    # 2b) Statistical analysis (frontier lab requirement)
    try:
        _run(
            [
                sys.executable,
                "scripts/tr119/statistical_analysis.py",
                "--cost-summary",
                str(processed_dir / "cost_energy_summary.json"),
            ]
        )
        manifest["statistical_analysis"] = str(processed_dir / "statistical_analysis.json")
    except subprocess.CalledProcessError as exc:
        manifest["statistical_analysis_error"] = str(exc)

    # 2c) Cost/energy validation
    if not args.skip_validation:
        try:
            _run(
                [
                    sys.executable,
                    "scripts/tr119/validate_cost_energy.py",
                    "--config",
                    str(cfg_path),
                ]
            )
            manifest["cost_energy_validation"] = str(processed_dir / "cost_energy_validation.json")
        except subprocess.CalledProcessError as exc:
            manifest["cost_energy_validation_error"] = str(exc)

    # 2d) Cost/energy deep analysis
    if not args.skip_deep_analysis:
        try:
            _run(
                [
                    sys.executable,
                    "scripts/tr119/cost_energy_analysis.py",
                    "--config",
                    str(cfg_path),
                ]
            )
            manifest["cost_energy_analysis"] = str(processed_dir / "cost_energy_analysis.json")
        except subprocess.CalledProcessError as exc:
            manifest["cost_energy_analysis_error"] = str(exc)

    if not args.no_plots:
        try:
            _run(
                [
                    sys.executable,
                    "scripts/tr119/visualize.py",
                    "--config",
                    str(cfg_path),
                ]
            )
            manifest["plots_dir"] = str(results_dir / "plots")
        except subprocess.CalledProcessError as exc:
            manifest["plots_error"] = str(exc)

    ended = time.time()
    manifest["ended_at"] = ended
    manifest["duration_s"] = ended - started

    out_path = processed_dir / f"experiment_manifest_{int(started)}.json"
    out_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Wrote TR119 manifest to {out_path}")

    if not args.no_report:
        try:
            report_out = resolve_repo_path(_REPO_ROOT, str(args.report_out))
            _run(
                [
                    sys.executable,
                    "scripts/tr119/generate_report.py",
                    "--config",
                    str(cfg_path),
                    "--output",
                    str(report_out),
                    "--manifest",
                    str(out_path),
                ]
            )
            print(f"Wrote TR119 report to {report_out}")
        except subprocess.CalledProcessError as exc:
            print(f"TR119 report generation failed: {exc}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


