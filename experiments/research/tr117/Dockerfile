# TR117 Reproducible Benchmark Environment
# CUDA 12.8, Python 3.13, TensorRT 10.12

FROM nvidia/cuda:12.8.0-cudnn9-devel-ubuntu22.04

# System dependencies
RUN apt-get update && apt-get install -y \
    python3.13 \
    python3.13-dev \
    python3-pip \
    git \
    wget \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set Python 3.13 as default
RUN update-alternatives --install /usr/bin/python python /usr/bin/python3.13 1 \
    && update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.13 1

# Install TensorRT (if not in base image)
# RUN pip install tensorrt==10.7.0

# Working directory
WORKDIR /workspace

# Copy requirements
COPY requirements_frozen.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements_frozen.txt

# Install Ollama (optional)
RUN curl -fsSL https://ollama.com/install.sh | sh

# Copy benchmark code
COPY . /workspace/tr117/

# Set environment variables
ENV PYTHONPATH=/workspace
ENV HF_HUB_OFFLINE=1
ENV CUDA_VISIBLE_DEVICES=0

# Entry point
WORKDIR /workspace/tr117
CMD ["bash"]

