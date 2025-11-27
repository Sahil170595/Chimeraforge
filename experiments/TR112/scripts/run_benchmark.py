"""
TR112 Runner: Rust vs Python Single-Agent Comparison

Automates the execution of TR112 (Rust vs Python Comparison).
1. Builds `demo_rust_agent` in release mode.
2. Runs Rust parameter sweep.
3. Runs Python parameter sweep (using src/python/banterhearts/demo_agent/run_demo.py).
"""

import subprocess
import sys
import shutil
import os
from pathlib import Path
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[3]
RUST_SRC = REPO_ROOT / "src" / "rust" / "demo_agent"
RUST_BINARY = RUST_SRC / "target" / "release" / "demo_rust_agent.exe"
PYTHON_SRC = REPO_ROOT / "src" / "python"
PYTHON_SCRIPT = PYTHON_SRC / "banterhearts" / "demo_agent" / "run_demo.py"
OUTPUT_ROOT = REPO_ROOT / "experiments" / "TR112" / "results"

def build_rust_binary():
    logger.info("Building Rust binary (release)...")
    try:
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
    # TR112 focused on a specific set, but we'll do a small sweep for verification
    gpu_layers = [60, 80]
    ctx_sizes = [512] # Keeping it smaller for quick verification
    temps = [0.8]

    total_configs = len(gpu_layers) * len(ctx_sizes) * len(temps) * 2 # Rust + Python
    current = 0

    for gpu in gpu_layers:
        for ctx in ctx_sizes:
            for temp in temps:
                config_slug = f"gpu{gpu}_ctx{ctx}_temp{str(temp).replace('.', 'p')}"
                
                # Rust Run
                current += 1
                rust_out = OUTPUT_ROOT / "rust" / config_slug
                logger.info(f"[{current}/{total_configs}] Running RUST {config_slug}...")
                rust_cmd = [
                    str(RUST_BINARY),
                    "--model", model,
                    "--runs", str(runs),
                    "--chimera-num-gpu", str(gpu),
                    "--chimera-num-ctx", str(ctx),
                    "--chimera-temperature", str(temp),
                    "--output-dir", str(rust_out)
                ]
                try:
                    subprocess.run(rust_cmd, check=True)
                except subprocess.CalledProcessError:
                    logger.error(f"Failed Rust run: {config_slug}")

                # Python Run
                current += 1
                python_out = OUTPUT_ROOT / "python" / config_slug
                logger.info(f"[{current}/{total_configs}] Running PYTHON {config_slug}...")
                
                # Set PYTHONPATH
                env = os.environ.copy()
                env["PYTHONPATH"] = str(PYTHON_SRC)
                
                python_cmd = [
                    sys.executable,
                    str(PYTHON_SCRIPT),
                    "--model", model,
                    "--runs", str(runs),
                    "--chimera-num-gpu", str(gpu),
                    "--chimera-num-ctx", str(ctx),
                    "--chimera-temperature", str(temp),
                    "--output-dir", str(python_out)
                ]
                try:
                    subprocess.run(python_cmd, env=env, check=True)
                except subprocess.CalledProcessError:
                    logger.error(f"Failed Python run: {config_slug}")

def main():
    if not shutil.which("cargo"):
        logger.error("Cargo not found.")
        sys.exit(1)
        
    build_rust_binary()
    run_sweep()
    logger.info("TR112 Benchmark Complete.")

if __name__ == "__main__":
    main()
