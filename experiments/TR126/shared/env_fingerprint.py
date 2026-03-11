"""Environment fingerprinting for TR126 cross-platform validation."""

from __future__ import annotations

import os
import platform
import sys
from typing import Any


def capture_environment() -> dict[str, Any]:
    """Capture full environment fingerprint for reproducibility and cross-platform comparison."""
    env: dict[str, Any] = {
        "platform": platform.platform(),
        "platform_system": platform.system(),
        "python_version": sys.version,
        "python_executable": sys.executable,
    }

    # PyTorch + CUDA
    try:
        import torch

        env["torch_version"] = torch.__version__
        env["cuda_available"] = torch.cuda.is_available()
        if torch.cuda.is_available():
            env["cuda_version"] = torch.version.cuda
            env["cudnn_version"] = str(torch.backends.cudnn.version())
            env["gpu_name"] = torch.cuda.get_device_name(0)
            props = torch.cuda.get_device_properties(0)
            vram = getattr(props, "total_memory", None) or getattr(
                props, "total_mem", 0
            )
            env["gpu_memory_gb"] = round(vram / 1e9, 2)
            env["gpu_compute_capability"] = list(torch.cuda.get_device_capability(0))
        else:
            env["cuda_version"] = None
            env["gpu_name"] = None
    except ImportError:
        env["torch_version"] = None
        env["cuda_available"] = False

    # Triton — the critical check for TR126
    try:
        import triton  # type: ignore

        env["triton_available"] = True
        env["triton_version"] = triton.__version__
    except ImportError:
        env["triton_available"] = False
        env["triton_version"] = None

    # torch.compile backend detection
    try:
        import torch._inductor  # type: ignore

        env["inductor_available"] = True
    except ImportError:
        env["inductor_available"] = False

    # Docker detection
    env["in_docker"] = (
        os.path.exists("/.dockerenv") or os.environ.get("container") == "docker"
    )
    env["triton_cache_dir"] = os.environ.get("TRITON_CACHE_DIR", "")
    env["cuda_visible_devices"] = os.environ.get("CUDA_VISIBLE_DEVICES", "")

    return env
