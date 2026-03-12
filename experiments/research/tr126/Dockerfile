# TR126: Docker/Linux + Triton Validation Environment
# Layers on top of NVIDIA's PyTorch container (already has PyTorch, CUDA, Triton,
# NumPy, Pandas, SciPy, Matplotlib, PyYAML). Only adds what's missing.
#
# Base image: nvcr.io/nvidia/pytorch:25.08-py3 (35GB, already pulled locally)
#   - PyTorch 2.8.0, CUDA 13.0, Triton 3.3.1, Python 3.12
#   - NumPy 1.26.4, Pandas 2.2.3, SciPy 1.15.3, Matplotlib 3.10.5
#
# Build:  docker build -t tr126 -f research/tr126/Dockerfile .
# Run:    docker run --rm --gpus all --ipc=host -v "${PWD}:/workspace" -w /workspace tr126 bash

FROM nvcr.io/nvidia/pytorch:25.08-py3

# ML libraries not in base image
RUN pip install --no-cache-dir \
    transformers>=4.46.3 \
    safetensors>=0.4.5 \
    tokenizers>=0.20.3

# Monitoring
RUN pip install --no-cache-dir \
    psutil>=6.1.0 \
    pynvml>=11.5.3

# Ollama (for Phase 3 backend comparison)
RUN apt-get update && apt-get install -y --no-install-recommends zstd \
    && rm -rf /var/lib/apt/lists/* \
    && curl -fsSL https://ollama.com/install.sh | sh

# Environment
ENV PYTHONPATH=/workspace
ENV CUDA_VISIBLE_DEVICES=0
ENV TRITON_CACHE_DIR=/tmp/triton_cache
ENV HF_HUB_OFFLINE=1

WORKDIR /workspace
CMD ["bash"]
