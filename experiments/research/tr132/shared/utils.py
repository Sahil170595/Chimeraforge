"""TR132 shared utilities — paths, constants, prompt generation."""

from __future__ import annotations

import logging
from pathlib import Path
import platform
import subprocess

import numpy as np

log = logging.getLogger("tr132.utils")

# ── Path anchors ──────────────────────────────────────────────────────
_DIR = Path(__file__).resolve().parent
_TR132 = _DIR.parent
_REPO = _TR132.parents[1]

TR132_RESULTS = _TR132 / "results"
TR132_CONFIG = _TR132 / "config.yaml"

# ── Tool paths ────────────────────────────────────────────────────────
NSYS_PATH = Path(
    "C:/Program Files/NVIDIA Corporation/"
    "Nsight Systems 2025.5.1/target-windows-x64/nsys.exe"
)

# ── nsys report types we extract ──────────────────────────────────────
NSYS_REPORTS = [
    "cuda_api_sum",
    "cuda_gpu_kern_sum",
    "cuda_gpu_mem_time_sum",
    "cuda_kern_exec_trace",
    "osrt_sum",
]

# ── Backend names used in TR132 ───────────────────────────────────────
BACKENDS = ["vllm", "tgi"]

# ── Seed paragraph for synthetic prompts (same as TR128-TR131) ────────
SEED_PARAGRAPH = (
    "The quick brown fox jumps over the lazy dog. "
    "In a world where technology evolves at an unprecedented pace, "
    "understanding the fundamental principles of computation becomes "
    "increasingly important. Machine learning models process vast "
    "amounts of data to identify patterns and make predictions. "
    "The transformer architecture introduced self-attention mechanisms "
    "that revolutionized natural language processing. Key-value caches "
    "store previously computed attention states to accelerate autoregressive "
    "generation. Memory bandwidth and compute capacity are the two primary "
    "bottlenecks in large language model inference. Context length determines "
    "how much information a model can consider when generating each token. "
    "Longer contexts require more memory for the key-value cache and more "
    "computation during the prefill phase. The quadratic scaling of attention "
    "with respect to sequence length is a fundamental computational challenge. "
)


def generate_prompt(target_tokens: int) -> str:
    """Generate an approximate-length prompt (no tokenizer)."""
    n_repeats = max(1, (target_tokens // 100) + 1)
    text = SEED_PARAGRAPH * n_repeats
    words = text.split()
    target_words = int(target_tokens / 1.3)
    return " ".join(words[:target_words])


def generate_prompts(
    n: int,
    rng: np.random.Generator | None = None,
    low: int = 100,
    high: int = 200,
) -> list[str]:
    """Generate n prompts with uniform random token-count targets."""
    if rng is None:
        rng = np.random.default_rng(42)
    lengths = rng.integers(low, high + 1, size=n)
    return [generate_prompt(int(length)) for length in lengths]


def find_latest_run(results_dir: str | Path) -> Path | None:
    """Find most recent timestamped run directory (YYYYMMDD_HHMMSS)."""
    results_dir = Path(results_dir)
    if not results_dir.is_dir():
        return None
    candidates = [
        p
        for p in results_dir.iterdir()
        if p.is_dir() and len(p.name) == 15 and p.name[8] == "_"
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.name)


def capture_environment() -> dict:
    """Capture environment fingerprint for manifest."""
    env = {
        "platform": platform.platform(),
        "python": platform.python_version(),
        "machine": platform.machine(),
    }
    # GPU
    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=name,memory.total,driver_version",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            parts = [p.strip() for p in result.stdout.strip().split(",")]
            env["gpu_name"] = parts[0] if len(parts) > 0 else "unknown"
            env["gpu_vram_mb"] = parts[1] if len(parts) > 1 else "unknown"
            env["gpu_driver"] = parts[2] if len(parts) > 2 else "unknown"
    except Exception:
        pass
    # nsys version
    try:
        result = subprocess.run(
            [str(NSYS_PATH), "--version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            env["nsys_version"] = result.stdout.strip()
    except Exception:
        pass
    # Docker version
    try:
        result = subprocess.run(
            ["docker", "--version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            env["docker_version"] = result.stdout.strip()
    except Exception:
        pass
    return env
