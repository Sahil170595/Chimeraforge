"""
TR111 Runner: Rust Single-Agent Benchmarks

Automates the execution of TR111 (Rust Single-Agent Performance).
1. Builds `demo_rust_agent` in release mode.
2. Runs parameter sweep:
   - Model: gemma3:latest
   - GPU Layers: [60, 80]
   - Context: [256, 512, 1024]
   - Temperature: [0.6, 0.8]
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
RUST_SRC = REPO_ROOT / "src" / "rust" / "demo_agent"
BINARY_PATH = RUST_SRC / "target" / "release" / "demo_rust_agent.exe"
OUTPUT_ROOT = REPO_ROOT / "experiments" / "TR111" / "results"

def build_rust_binary():
    logger.info("Building Rust binary (release)...")
    try:
        subprocess.run(
            ["cargo", "build", "--release"],
            cwd=RUST_SRC,
            check=True,
            capture_output=False
        )
    except subprocess.CalledProcessError as e:
        logger.error("Failed to build Rust binary.")
        sys.exit(1)

def run_sweep():
    model = "gemma3:latest"
    runs = 5
    gpu_layers = [60, 80]
    ctx_sizes = [256, 512, 1024]
    temps = [0.6, 0.8]

    total_configs = len(gpu_layers) * len(ctx_sizes) * len(temps)
    current = 0

    for gpu in gpu_layers:
        for ctx in ctx_sizes:
            for temp in temps:
                current += 1
                config_slug = f"gpu{gpu}_ctx{ctx}_temp{str(temp).replace('.', 'p')}"
                output_dir = OUTPUT_ROOT / config_slug
                
                logger.info(f"[{current}/{total_configs}] Running {config_slug}...")
                
                cmd = [
                    str(BINARY_PATH),
                    "--model", model,
                    "--runs", str(runs),
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
        logger.error("Cargo not found. Please install Rust.")
        sys.exit(1)
        
    build_rust_binary()
    run_sweep()
    logger.info("TR111 Benchmark Complete.")

if __name__ == "__main__":
    main()
