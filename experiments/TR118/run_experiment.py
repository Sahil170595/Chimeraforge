#!/usr/bin/env python3
"""
TR118: End-to-end experiment orchestrator.

Runs the full local-first pipeline:
  1) Benchmark (includes ONNX export + TRT builds when configured)
  2) Analyze results
  3) Validate accuracy (perplexity gate)
  4) Generate plots (optional)

Artifacts are written under `scripts/tr118/results/` as configured.
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

from scripts.tr118.artifact_utils import resolve_repo_path


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


def _latest_jsonl(results_dir: Path) -> Path | None:
    raw_dir = results_dir / "raw"
    files = sorted(raw_dir.glob("bench_*.jsonl"), key=lambda p: p.stat().st_mtime)
    return files[-1] if files else None


def _latest_jsonl_for_mode(results_dir: Path, mode: str) -> Path | None:
    raw_dir = results_dir / "raw"
    files = sorted(raw_dir.glob(f"bench_{mode}_*.jsonl"), key=lambda p: p.stat().st_mtime)
    return files[-1] if files else None


def main() -> int:
    parser = argparse.ArgumentParser(description="TR118 end-to-end runner")
    parser.add_argument(
        "--config",
        default="scripts/tr118/configs/matrix_postdoc.yaml",
        help="TR118 config yaml",
    )
    parser.add_argument(
        "--prompt-config",
        default=None,
        help="Prompt config yaml (defaults to config.benchmark.prompt_config_path)",
    )
    parser.add_argument(
        "--device",
        default="cpu",
        help="Device for PyTorch perplexity baseline (cpu/cuda)",
    )
    parser.add_argument(
        "--modes",
        nargs="*",
        choices=["prefill", "generate"],
        default=None,
        help="Benchmark modes to run (defaults to config.benchmark.modes or config.benchmark.mode)",
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
        default="reports/generated/Technical_Report_118.md",
        help="Where to write the TR118 report",
    )
    parser.add_argument(
        "--skip-accuracy",
        action="store_true",
        help="Skip perplexity validation step",
    )
    parser.add_argument(
        "--force-export",
        action="store_true",
        help="Force re-export ONNX once at the start of this run (passed to first benchmark mode only).",
    )
    parser.add_argument(
        "--force-trt-rebuild",
        action="store_true",
        help="Force TensorRT rebuild once at the start of this run (passed to first benchmark mode only).",
    )
    args = parser.parse_args()

    cfg_path = resolve_repo_path(_REPO_ROOT, str(args.config))
    cfg = _load_yaml(cfg_path)
    results_dir = resolve_repo_path(_REPO_ROOT, str(cfg["output"]["results_dir"]))
    processed_dir = results_dir / "processed"
    processed_dir.mkdir(parents=True, exist_ok=True)

    prompt_cfg_path = (
        resolve_repo_path(_REPO_ROOT, str(args.prompt_config))
        if args.prompt_config
        else resolve_repo_path(
            _REPO_ROOT,
            str(cfg.get("benchmark", {}).get("prompt_config_path", "scripts/tr117/configs/matrix_tier3.yaml")),
        )
    )

    started = time.time()
    run_id = int(started)
    manifest: dict[str, Any] = {
        "tr": "TR118",
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
            "pycuda": _try_version("pycuda"),
            "datasets": _try_version("datasets"),
            "numpy": _try_version("numpy"),
            "pandas": _try_version("pandas"),
            "scipy": _try_version("scipy"),
            "matplotlib": _try_version("matplotlib"),
        },
    }

    # Persist exact config snapshot used.
    cfg_snapshot_path = processed_dir / f"config_used_{int(started)}.yaml"
    cfg_snapshot_path.write_text(cfg_path.read_text(encoding="utf-8"), encoding="utf-8")
    manifest["config_snapshot_path"] = str(cfg_snapshot_path)

    modes = args.modes
    if modes is None:
        cfg_modes = cfg.get("benchmark", {}).get("modes")
        if isinstance(cfg_modes, list) and cfg_modes:
            modes = [str(m) for m in cfg_modes]
        else:
            modes = [str(cfg.get("benchmark", {}).get("mode", "prefill"))]

    runs: dict[str, dict[str, Any]] = {}

    # 1) Benchmark + analyze (per mode)
    for idx, mode in enumerate(modes):
        env = None
        if idx == 0 and (args.force_export or args.force_trt_rebuild):
            env = os.environ.copy()
            if args.force_export:
                env["BANTER_TR118_FORCE_EXPORT"] = "1"
            if args.force_trt_rebuild:
                env["BANTER_TR118_FORCE_TRT_REBUILD"] = "1"
        _run(
            [
                sys.executable,
                "scripts/tr118/run_benchmark.py",
                "--config",
                str(cfg_path),
                "--prompt-config",
                str(prompt_cfg_path),
                "--mode",
                str(mode),
                "--run-id",
                str(run_id),
            ],
            env=env,
        )
        raw_path = results_dir / "raw" / f"bench_{mode}_{run_id}.jsonl"
        if not raw_path.exists():
            raw_path = _latest_jsonl_for_mode(results_dir, str(mode)) or _latest_jsonl(results_dir)
        runs[str(mode)] = {
            "raw_results_path": str(raw_path) if raw_path else None,
            "latency_summary_path": str(processed_dir / f"latency_summary_{mode}.csv"),
            "statistical_analysis_path": str(processed_dir / f"statistical_analysis_{mode}.json"),
        }

        analyze_cmd = [
            sys.executable,
            "scripts/tr118/analyze_results.py",
            "--config",
            str(cfg_path),
            "--mode",
            str(mode),
        ]
        if raw_path:
            analyze_cmd += ["--raw", str(raw_path)]
        _run(analyze_cmd)

        if not args.no_plots:
            try:
                _run(
                    [
                        sys.executable,
                        "scripts/tr118/visualize.py",
                        "--config",
                        str(cfg_path),
                        "--mode",
                        str(mode),
                    ]
                )
                manifest["plots_dir"] = str(results_dir / "plots")
            except subprocess.CalledProcessError as exc:
                manifest["plots_error"] = str(exc)

    manifest["runs"] = runs
    manifest["export_metadata_path"] = str(processed_dir / f"export_metadata_{run_id}.json")
    manifest["trt_build_metadata_path"] = str(processed_dir / f"trt_build_metadata_{run_id}.json")

    # 3) Accuracy validation
    if not args.skip_accuracy:
        _run(
            [
                sys.executable,
                "scripts/tr118/validate_accuracy.py",
                "--config",
                str(cfg_path),
                "--device",
                str(args.device),
            ]
        )
        manifest["perplexity_results_csv"] = str(processed_dir / "perplexity_results.csv")
        manifest["perplexity_results_json"] = str(processed_dir / "perplexity_results.json")

    ended = time.time()
    manifest["ended_at"] = ended
    manifest["duration_s"] = ended - started

    out_path = processed_dir / f"experiment_manifest_{int(started)}.json"
    out_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Wrote manifest to {out_path}")

    # 4) PublishReady report (optional; reads artifacts + this manifest)
    if not args.no_report:
        try:
            report_out = resolve_repo_path(_REPO_ROOT, str(args.report_out))
            _run(
                [
                    sys.executable,
                    "scripts/tr118/generate_report.py",
                    "--config",
                    str(cfg_path),
                    "--output",
                    str(report_out),
                    "--manifest",
                    str(out_path),
                ]
            )
            print(f"Wrote report to {report_out}")
        except subprocess.CalledProcessError as exc:
            print(f"Report generation failed: {exc}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
