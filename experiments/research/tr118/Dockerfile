# TR118 Reproducible Environment (ONNX + TensorRT)
# CUDA 12.8, Python 3.13

FROM nvidia/cuda:12.8.0-cudnn9-devel-ubuntu22.04

RUN apt-get update && apt-get install -y \
    python3.13 \
    python3.13-dev \
    python3-pip \
    git \
    && rm -rf /var/lib/apt/lists/*

RUN update-alternatives --install /usr/bin/python python /usr/bin/python3.13 1 \
    && update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.13 1

WORKDIR /workspace

COPY scripts/tr118/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . /workspace/banterhearts/

ENV PYTHONPATH=/workspace/banterhearts
ENV CUDA_VISIBLE_DEVICES=0

WORKDIR /workspace/banterhearts/scripts/tr118
CMD ["bash"]

