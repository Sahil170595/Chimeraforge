"""TR133 shared utilities — paths, constants, helpers."""

from __future__ import annotations

import logging
from pathlib import Path
import platform
import subprocess

log = logging.getLogger("tr133.utils")

# ── Path anchors ──────────────────────────────────────────────────────
_DIR = Path(__file__).resolve().parent
_TR133 = _DIR.parent
_REPO = _TR133.parents[1]

TR133_RESULTS = _TR133 / "results"

# ── Quant ordering (highest precision first) ──────────────────────────
QUANT_LEVELS = ["FP16", "Q8_0", "Q6_K", "Q5_K_M", "Q4_K_M", "Q3_K_S", "Q2_K"]

# Approximate bits-per-weight
QUANT_BPW: dict[str, float] = {
    "FP16": 16.0,
    "Q8_0": 8.0,
    "Q6_K": 6.5,
    "Q5_K_M": 5.5,
    "Q4_K_M": 4.5,
    "Q3_K_S": 3.5,
    "Q2_K": 2.5,
}

# ── Backend names ─────────────────────────────────────────────────────
BACKENDS = ["ollama", "vllm", "tgi"]

# ── Model registry (params in billions) ───────────────────────────────
MODEL_PARAMS_B: dict[str, float] = {
    "qwen2.5-0.5b": 0.49,
    "llama3.2-1b": 1.24,
    "qwen2.5-1.5b": 1.54,
    "phi-2": 2.78,
    "qwen2.5-3b": 3.09,
    "llama3.2-3b": 3.21,
    "llama3.1-8b": 8.03,
}

# Architecture metadata for KV-cache formula
MODEL_ARCH: dict[str, dict] = {
    "qwen2.5-0.5b": {"n_layers": 24, "n_kv_heads": 2, "d_head": 64},
    "llama3.2-1b": {"n_layers": 16, "n_kv_heads": 8, "d_head": 64},
    "qwen2.5-1.5b": {"n_layers": 28, "n_kv_heads": 2, "d_head": 128},
    "phi-2": {"n_layers": 32, "n_kv_heads": 32, "d_head": 80},
    "qwen2.5-3b": {"n_layers": 36, "n_kv_heads": 2, "d_head": 128},
    "llama3.2-3b": {"n_layers": 28, "n_kv_heads": 8, "d_head": 128},
    "llama3.1-8b": {"n_layers": 32, "n_kv_heads": 8, "d_head": 128},
}


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
    return env


def repo_root() -> Path:
    """Return the repository root."""
    return _REPO
