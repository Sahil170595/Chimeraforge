# Triton Docker Benchmark Summary (2025-10-02) - Attempted to run `scripts/compilation/run_compilation_benchmarks.py` inside NVIDIA's PyTorch 24.07 CUDA container (`nvcr.io/nvidia/pytorch:24.07-py3`).
- Container Python version is 3.10; our package requires >=3.11, so editable install failed (`chimera-heart` requires >=3.11).
- Alternate approach (install requirements and set `PYTHONPATH`) failed because the environment is pinned to `cryptography==41.0.8`, which is not available for Python 3.10 in that image.
- Result: no new benchmark outputs were produced; further work would require a Python 3.11 CUDA image or a conda environment inside the container with Python 3.11.
