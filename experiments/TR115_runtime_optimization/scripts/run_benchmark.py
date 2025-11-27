"""
TR115 Runner: Rust Runtime Optimization Benchmarks

Automates the execution of TR115 (Rust Async Runtime Performance).
1. Iterates through runtimes: tokio-default, tokio-localset, smol, async-std, smol-1kb.
2. Recompiles `Demo_rust_multiagent` with specific feature flags for each runtime.
3. Runs the benchmark (chimera_homo scenario).
"""

import subprocess
import sys
import shutil
from pathlib import Path
import logging
import time

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[3]
RUST_SRC = REPO_ROOT / "src" / "rust" / "demo_multiagent"
BINARY_PATH = RUST_SRC / "target" / "release" / "Demo_rust_multiagent.exe"
OUTPUT_ROOT = REPO_ROOT / "experiments" / "TR115_runtime_optimization" / "results"

RUNTIMES = [
    "runtime-tokio-default",
    "runtime-tokio-localset",
    "runtime-smol",
    "runtime-async-std",
    "runtime-smol-1kb"
]

def build_runtime(runtime_feature):
    logger.info(f"Building Rust binary for {runtime_feature}...")
    try:
        # Clean first to ensure feature flags apply
        subprocess.run(["cargo", "clean", "-p", "Demo_rust_multiagent"], cwd=RUST_SRC, check=True, capture_output=True)
        
        cmd = [
            "cargo", "build", "--release",
            "--no-default-features",
            "--features", runtime_feature
        ]
        subprocess.run(cmd, cwd=RUST_SRC, check=True)
    except subprocess.CalledProcessError:
        logger.error(f"Failed to build for {runtime_feature}")
        return False
    return True

def run_benchmark(runtime_name):
    model = "gemma3:latest"
    runs = 5
    scenario = "chimera_homo"
    gpu = 80
    ctx = 512
    temp = 1.0
    
    config_slug = f"{runtime_name}_{scenario}"
    output_dir = OUTPUT_ROOT / runtime_name / config_slug
    
    logger.info(f"Running benchmark for {runtime_name}...")
    
    cmd = [
        str(BINARY_PATH),
        "--model", model,
        "--runs", str(runs),
        "--scenario", scenario,
        "--collector-ollama-url", "http://localhost:11434",
        "--insight-ollama-url", "http://localhost:11435",
        "--chimera-num-gpu", str(gpu),
        "--chimera-num-ctx", str(ctx),
        "--chimera-temperature", str(temp),
        "--output-dir", str(output_dir)
    ]
    
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError:
        logger.error(f"Failed run for {runtime_name}")

def main():
    if not shutil.which("cargo"):
        logger.error("Cargo not found.")
        sys.exit(1)
        
    for runtime in RUNTIMES:
        logger.info(f"=== Starting Suite for {runtime} ===")
        if build_runtime(runtime):
            run_benchmark(runtime)
            
    logger.info("TR115 Benchmark Complete.")

if __name__ == "__main__":
    main()
