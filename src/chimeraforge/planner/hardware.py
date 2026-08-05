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
    bandwidth_gbps: float  # Memory bandwidth in GB/s (decode/TPOT is bound by this)
    cost_per_hour: float  # $/hr (cloud rental or amortised consumer)
    fp16_tflops: float = 0.0  # Dense FP16 Tensor TFLOPS, FP32 accumulate (prefill/TTFT)


# Reference GPU - all TR measurements collected on this card
REFERENCE_GPU = "RTX 4080 12GB"

# fp16_tflops: dense FP16 Tensor Core, FP32-accumulate, non-sparse. Datacenter
# values are official datasheets (A100 312, H100 SXM 989, L4 121, T4 65). H200
# shares H100's GH100 compute die, so 989 (only its memory differs). B200 and
# MI300X datasheets print only a with-sparsity figure, so dense = that / 2 (B200
# 4500 -> 2250; MI300X's sheet also prints the dense 1307 directly). Consumer
# Ada/Blackwell are derived as dense = 2x FP32 shader, which equals the RTX
# Blackwell whitepaper's FP32-accumulate row (RTX 4090 165.2, RTX 5090 209.5);
# consumer Ampere use the FP32-accumulate dense rate (half the FP16-accumulate
# figure) to stay on one basis. Datacenter $/hr are approximate on-demand cloud
# rates; consumer $/hr are amortised card cost. B200 uses NVIDIA's HGX B200
# per-GPU datasheet figures (180 GB / 7.7 TB/s), not the 192 GB raw-stack number.
# Approximate; prefill MFU and the `measure` path absorb the slack.
GPU_DB: dict[str, GPUSpec] = {
    # Consumer - NVIDIA Ada
    "RTX 4060 8GB": GPUSpec("RTX 4060 8GB", 8.0, 272.0, 0.020, 30.2),
    "RTX 4060 Ti 8GB": GPUSpec("RTX 4060 Ti 8GB", 8.0, 288.0, 0.025, 44.1),
    "RTX 4060 Ti 16GB": GPUSpec("RTX 4060 Ti 16GB", 16.0, 288.0, 0.030, 44.1),
    "RTX 4070 12GB": GPUSpec("RTX 4070 12GB", 12.0, 504.0, 0.030, 58.4),
    "RTX 4070 Ti 12GB": GPUSpec("RTX 4070 Ti 12GB", 12.0, 504.0, 0.035, 80.2),
    "RTX 4080 12GB": GPUSpec("RTX 4080 12GB", 12.0, 556.0, 0.035, 80.2),
    "RTX 4080 16GB": GPUSpec("RTX 4080 16GB", 16.0, 717.0, 0.045, 97.5),
    "RTX 4090 24GB": GPUSpec("RTX 4090 24GB", 24.0, 1008.0, 0.060, 165.2),
    # Consumer - NVIDIA Blackwell (GDDR7)
    "RTX 5070 12GB": GPUSpec("RTX 5070 12GB", 12.0, 672.0, 0.030, 61.7),
    "RTX 5070 Ti 16GB": GPUSpec("RTX 5070 Ti 16GB", 16.0, 896.0, 0.038, 87.9),
    "RTX 5080 16GB": GPUSpec("RTX 5080 16GB", 16.0, 960.0, 0.045, 112.6),
    "RTX 5090 32GB": GPUSpec("RTX 5090 32GB", 32.0, 1792.0, 0.075, 209.5),
    # Consumer - NVIDIA Ampere
    "RTX 3090 24GB": GPUSpec("RTX 3090 24GB", 24.0, 936.0, 0.040, 71.0),
    "RTX 3080 10GB": GPUSpec("RTX 3080 10GB", 10.0, 760.0, 0.025, 59.5),
    # Data-center - NVIDIA
    "A100 40GB": GPUSpec("A100 40GB", 40.0, 1555.0, 1.10, 312.0),
    "A100 80GB": GPUSpec("A100 80GB", 80.0, 2039.0, 1.60, 312.0),
    "H100 80GB": GPUSpec("H100 80GB", 80.0, 3352.0, 2.50, 989.0),
    "H200 141GB": GPUSpec("H200 141GB", 141.0, 4800.0, 3.50, 989.0),
    "B200 180GB": GPUSpec("B200 180GB", 180.0, 7700.0, 5.50, 2250.0),
    "L4 24GB": GPUSpec("L4 24GB", 24.0, 300.0, 0.50, 121.0),
    "T4 16GB": GPUSpec("T4 16GB", 16.0, 320.0, 0.35, 65.0),
    # Data-center - AMD
    "MI300X 192GB": GPUSpec("MI300X 192GB", 192.0, 5300.0, 2.00, 1307.0),
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
