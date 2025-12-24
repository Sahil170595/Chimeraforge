#!/usr/bin/env python3
"""
TR118 Validation: Benchmark the custom 45M parameter model.
"""

from pathlib import Path
import subprocess
import sys

import yaml


def main():
    repo_root = Path(__file__).resolve().parents[2]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))


    # Config
    base_cfg_path = repo_root / "scripts/tr118/configs/matrix_postdoc.yaml"
    model_path = repo_root / "models/gpt2-45m"
    results_dir = repo_root / "scripts/tr118/results/validation_45m"
    artifacts_dir = repo_root / "artifacts/validation_45m"

    # Load base config
    with open(base_cfg_path) as f:
        config = yaml.safe_load(f)

    # Override
    config["model"] = {
        "name": str(model_path),
        "path": str(model_path),
        "description": "Custom 45M param model for crossover validation"
    }
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
    gen_cfg_path = results_dir / "config_45m.yaml"
    with open(gen_cfg_path, "w") as f:
        yaml.dump(config, f)

    print("Running benchmark for gpt2-45m...")

    # Run experiment
    cmd = [
        sys.executable,
        "scripts/tr118/run_experiment.py",
        "--config", str(gen_cfg_path),
        "--device", "cuda",
        "--modes", "prefill", "generate", # Run both
        "--no-report" # We'll manually analyze
    ]

    subprocess.run(cmd, check=True, cwd=str(repo_root))

if __name__ == "__main__":
    main()
