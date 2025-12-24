#!/usr/bin/env python3
"""
TR118 helper: Fix/verify PyCUDA on Windows.

PyCUDA's `_driver` extension depends on CUDA DLLs (e.g. curand64_10.dll). On
modern Python, extension module dependencies may not be resolved via PATH, so
we add CUDA `bin/` directories via `os.add_dll_directory()` and then verify.
"""

from __future__ import annotations

import os
from pathlib import Path
import sys


def main() -> int:
    if os.name != "nt":
        print("Not Windows; nothing to do.")
        return 0

    repo_root = Path(__file__).resolve().parents[2]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    from scripts.tr118.trt_inference import ensure_cuda_dll_search_path

    print("CUDA env:")
    for k in sorted([k for k in os.environ.keys() if k.upper().startswith("CUDA_PATH")]):
        print(f"  {k}={os.environ.get(k)}")

    added = ensure_cuda_dll_search_path()
    print("Added DLL dirs:")
    for p in added:
        print(f"  {p}")

    try:
        import pycuda.autoinit  # type: ignore  # noqa: F401
        import pycuda.driver as cuda  # type: ignore

        n = cuda.Device.count()
        name = cuda.Device(0).name() if n else None
        print(f"PyCUDA OK: device_count={n}, device0={name}")
        return 0
    except Exception as exc:
        print(f"PyCUDA FAILED: {type(exc).__name__}: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

