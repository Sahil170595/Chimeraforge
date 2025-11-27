"""
TR114 Runner: Rust Multi-Agent Benchmarks

Automates the execution of TR114 (Rust Multi-Agent Performance).
1. Builds `Demo_rust_multiagent` in release mode.
2. Runs parameter sweep across scenarios:
   - baseline_vs_chimera
   - chimera_homo
   - chimera_hetero
"""

import subprocess
import sys
import shutil
from pathlib import Path
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[3]
RUST_SRC = REPO_ROOT / "src" / "rust" / "demo_multiagent"
BINARY_PATH = RUST_SRC / "target" / "release" / "Demo_rust_multiagent.exe"
OUTPUT_ROOT = REPO_ROOT / "experiments" / "TR114" / "results"

def build_rust_binary():
    logger.info("Building Rust binary (release)...")
    try:
        # Default features (tokio-default)
        subprocess.run(
            ["cargo", "build", "--release"],
            cwd=RUST_SRC,
            check=True,
            capture_output=False
        )
    except subprocess.CalledProcessError:
        logger.error("Failed to build Rust binary.")
        sys.exit(1)

def run_sweep():
    model = "gemma3:latest"
    runs = 5
    scenarios = ["baseline_vs_chimera", "chimera_homo", "chimera_hetero"]
    
    # Standard config for TR114
    gpu = 80
    ctx = 512
    temp = 1.0

    total_configs = len(scenarios)
    current = 0

    for scenario in scenarios:
        current += 1
        config_slug = f"{scenario}_gpu{gpu}_ctx{ctx}"
        output_dir = OUTPUT_ROOT / config_slug
        
        logger.info(f"[{current}/{total_configs}] Running {config_slug}...")
        
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
            logger.error(f"Failed run: {config_slug}")

def main():
    if not shutil.which("cargo"):
        logger.error("Cargo not found.")
        sys.exit(1)
        
    build_rust_binary()
    run_sweep()
    logger.info("TR114 Benchmark Complete.")

if __name__ == "__main__":
    main()
