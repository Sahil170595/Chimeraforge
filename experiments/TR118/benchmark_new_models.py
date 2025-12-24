#!/usr/bin/env python3
"""
Benchmark all new models for TR118v2.1 crossover validation.

Runs benchmarks for: gpt2-5m, gpt2-25m, gpt2-50m, gpt2-75m, gpt2-100m
Uses the same pipeline as run_validation_45m.py
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.tr118.artifact_utils import resolve_repo_path


def benchmark_model(model_name: str, model_path: Path) -> int:
    """Benchmark a single model."""
    print(f"\n{'='*60}")
    print(f"Benchmarking {model_name}")
    print(f"{'='*60}")
    
    # Setup paths
    base_cfg_path = resolve_repo_path(_REPO_ROOT, "scripts/tr118/configs/matrix_postdoc.yaml")
    results_dir = _REPO_ROOT / "scripts/tr118/results/tr118v2_crossover" / model_name
    artifacts_dir = _REPO_ROOT / "artifacts/tr118v2_crossover" / model_name
    
    # Load base config
    with open(base_cfg_path, encoding="utf-8") as f:
        config: dict[str, Any] = yaml.safe_load(f)
    
    # Override model config
    # Use full path for 'name' since tokenizer loader uses model["name"]
    config["model"] = {
        "name": str(model_path),
        "path": str(model_path),
        "description": f"Custom {model_name} model for crossover validation"
    }
    
    # Override output paths
    config["output"] = {
        "results_dir": str(results_dir),
        "onnx_dir": str(artifacts_dir / "onnx"),
        "tensorrt_dir": str(artifacts_dir / "tensorrt")
    }
    
    # Ensure dirs exist
    results_dir.mkdir(parents=True, exist_ok=True)
    (artifacts_dir / "onnx").mkdir(parents=True, exist_ok=True)
    (artifacts_dir / "tensorrt").mkdir(parents=True, exist_ok=True)
    
    # Write temp config
    gen_cfg_path = results_dir / f"config_{model_name}.yaml"
    with open(gen_cfg_path, "w", encoding="utf-8") as f:
        yaml.dump(config, f)
    
    print(f"Config: {gen_cfg_path}")
    print(f"Results: {results_dir}")
    print(f"Artifacts: {artifacts_dir}")
    
    # Run experiment
    cmd = [
        sys.executable,
        "scripts/tr118/run_experiment.py",
        "--config", str(gen_cfg_path),
        "--device", "cuda",
        "--modes", "prefill", "generate",
    ]
    
    print(f"\nRunning: {' '.join(cmd)}")
    try:
        result = subprocess.run(cmd, check=True, cwd=str(_REPO_ROOT))
        print(f"[OK] {model_name} benchmark completed")
        return 0
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] {model_name} benchmark failed: {e}")
        return 1
    except KeyboardInterrupt:
        print(f"\n[INTERRUPTED] {model_name} benchmark cancelled")
        return 1


def main() -> int:
    """Benchmark all new models."""
    # Models to benchmark
    models = [
        ("gpt2-5m", Path("models/gpt2-5m")),
        ("gpt2-25m", Path("models/gpt2-25m")),
        ("gpt2-50m", Path("models/gpt2-50m")),
        ("gpt2-75m", Path("models/gpt2-75m")),
        ("gpt2-100m", Path("models/gpt2-100m")),
    ]
    
    print("=" * 60)
    print("TR118v2.1 CROSSOVER VALIDATION BENCHMARKS")
    print("=" * 60)
    print(f"Models to benchmark: {len(models)}")
    for name, path in models:
        full_path = _REPO_ROOT / path
        exists = full_path.exists()
        status = "OK" if exists else "MISSING"
        print(f"  {name:15} {str(path):20} [{status}]")
    print()
    
    # Check all models exist
    missing = [name for name, path in models if not (_REPO_ROOT / path).exists()]
    if missing:
        print(f"[ERROR] Missing models: {', '.join(missing)}")
        print("Run build_4_data_points.py first to build models")
        return 1
    
    # Benchmark each model
    results = []
    for model_name, model_path in models:
        full_path = _REPO_ROOT / model_path
        exit_code = benchmark_model(model_name, full_path)
        results.append((model_name, exit_code))
    
    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    successful = [name for name, code in results if code == 0]
    failed = [name for name, code in results if code != 0]
    
    print(f"Successful: {len(successful)}/{len(models)}")
    for name in successful:
        print(f"  [OK] {name}")
    
    if failed:
        print(f"\nFailed: {len(failed)}/{len(models)}")
        for name in failed:
            print(f"  [ERROR] {name}")
    
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())

