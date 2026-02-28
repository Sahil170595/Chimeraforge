"""GPU hardware specifications database.

Provides VRAM, memory bandwidth, and approximate hourly cost for
consumer and data-center GPUs. Bandwidth ratios relative to the
reference GPU (RTX 4080) are used to extrapolate throughput for
untested hardware.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GPUSpec:
    name: str
    vram_gb: float
    bandwidth_gbps: float  # Memory bandwidth in GB/s
    cost_per_hour: float   # $/hr (cloud rental or amortised consumer)


# Reference GPU — all TR measurements collected on this card
REFERENCE_GPU = "RTX 4080 12GB"

GPU_DB: dict[str, GPUSpec] = {
    # Consumer — NVIDIA
    "RTX 4060 8GB": GPUSpec("RTX 4060 8GB", 8.0, 272.0, 0.020),
    "RTX 4060 Ti 8GB": GPUSpec("RTX 4060 Ti 8GB", 8.0, 288.0, 0.025),
    "RTX 4060 Ti 16GB": GPUSpec("RTX 4060 Ti 16GB", 16.0, 288.0, 0.030),
    "RTX 4070 12GB": GPUSpec("RTX 4070 12GB", 12.0, 504.0, 0.030),
    "RTX 4070 Ti 12GB": GPUSpec("RTX 4070 Ti 12GB", 12.0, 504.0, 0.035),
    "RTX 4080 12GB": GPUSpec("RTX 4080 12GB", 12.0, 556.0, 0.035),
    "RTX 4080 16GB": GPUSpec("RTX 4080 16GB", 16.0, 717.0, 0.045),
    "RTX 4090 24GB": GPUSpec("RTX 4090 24GB", 24.0, 1008.0, 0.060),
    "RTX 3090 24GB": GPUSpec("RTX 3090 24GB", 24.0, 936.0, 0.040),
    "RTX 3080 10GB": GPUSpec("RTX 3080 10GB", 10.0, 760.0, 0.025),
    # Data-center — NVIDIA
    "A100 40GB": GPUSpec("A100 40GB", 40.0, 1555.0, 1.10),
    "A100 80GB": GPUSpec("A100 80GB", 80.0, 2039.0, 1.60),
    "H100 80GB": GPUSpec("H100 80GB", 80.0, 3352.0, 2.50),
    "L4 24GB": GPUSpec("L4 24GB", 24.0, 300.0, 0.50),
    "T4 16GB": GPUSpec("T4 16GB", 16.0, 320.0, 0.35),
}


def get_gpu(name: str) -> GPUSpec | None:
    """Look up GPU by name (case-insensitive partial match)."""
    name_lower = name.lower()
    for key, spec in GPU_DB.items():
        if key.lower() == name_lower:
            return spec
    for key, spec in GPU_DB.items():
        if name_lower in key.lower() or key.lower() in name_lower:
            return spec
    return None


def bandwidth_ratio(target_gpu: str) -> float:
    """Throughput scaling ratio: target bandwidth / reference bandwidth.

    Used to extrapolate throughput from RTX 4080 measurements to other GPUs.
    Returns 1.0 for the reference GPU or unknown GPUs.
    """
    ref = GPU_DB.get(REFERENCE_GPU)
    target = get_gpu(target_gpu)
    if ref is None or target is None:
        return 1.0
    return target.bandwidth_gbps / ref.bandwidth_gbps
