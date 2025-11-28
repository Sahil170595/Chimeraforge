"""One-shot system profiling utilities."""

from __future__ import annotations

from typing import Dict, List

import psutil

from ..nvidia_tools import get_gpu_snapshots


class SystemProfiler:
    def snapshot(self) -> Dict[str, object]:
        mem = psutil.virtual_memory()
        load = psutil.getloadavg() if hasattr(psutil, "getloadavg") else (0.0, 0.0, 0.0)
        return {
            "cpu_percent": psutil.cpu_percent(interval=None),
            "load_avg": load,
            "memory": {
                "percent": mem.percent,
                "used_mb": mem.used / (1024 * 1024),
                "available_mb": mem.available / (1024 * 1024),
            },
            "gpus": get_gpu_snapshots(),
        }
