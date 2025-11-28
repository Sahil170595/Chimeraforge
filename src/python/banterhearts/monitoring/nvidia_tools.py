"""Lightweight NVML helpers for GPU telemetry."""

from __future__ import annotations

from typing import Dict, List
import warnings

# Silence pynvml deprecation warnings; switchable to nvidia-ml-py when available.
warnings.filterwarnings("ignore", category=FutureWarning, message=".*pynvml.*deprecated.*")
try:
    import pynvml
except Exception:  # pragma: no cover - optional dependency
    pynvml = None


def _init_nvml() -> bool:
    if not pynvml:
        return False
    try:
        pynvml.nvmlInit()
        return True
    except Exception:
        return False


def get_gpu_snapshots() -> List[Dict[str, float]]:
    """Return per-GPU telemetry or an empty list if NVML is unavailable."""
    if not _init_nvml():
        return []

    snapshots: List[Dict[str, float]] = []
    try:
        count = pynvml.nvmlDeviceGetCount()
        for idx in range(count):
            handle = pynvml.nvmlDeviceGetHandleByIndex(idx)
            util = pynvml.nvmlDeviceGetUtilizationRates(handle)
            mem = pynvml.nvmlDeviceGetMemoryInfo(handle)
            temp = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
            snapshots.append(
                {
                    "gpu_index": idx,
                    "utilization": float(util.gpu),
                    "mem_used_mb": mem.used / (1024 * 1024),
                    "mem_total_mb": mem.total / (1024 * 1024),
                    "temperature_c": float(temp),
                }
            )
    finally:
        try:
            pynvml.nvmlShutdown()
        except Exception:
            pass

    return snapshots
