# Triton 25.08 Transformer CUDA Benchmark (2025-10-02) - Image: `nvcr.io/nvidia/tritonserver:25.08-trtllm-python-py3`
- Runtime stack: Python 3.12.3 | Torch 2.8.0 | TensorRT 10.12.0.36 | CUDA 12.8 runtime
- Command: `scripts/compilation/run_compilation_benchmarks.py --model transformer --device cuda --backends eager,jit,torch_compile,onnx,tensorrt`
- Warnings: `pip` downgraded some preinstalled components; TensorRT-LLM requirements complain but run completed.
- Follow-up Torch-TensorRT run (separate container): `python scripts/compilation/run_tensorrt_docker.py --model transformer --backends eager,jit,torch_compile,tensorrt --runs 10 --warmup-runs 3` - Container: `nvcr.io/nvidia/pytorch:25.08-py3` - Runtime stack: Torch 2.8.0a0+34c6371 | TensorRT 10.13.2.6 | torch-tensorrt 2.8.0a0 (GitHub release index) | Backend | Mean latency (ms) | Std (ms) | Compile time (s) | Success | Notes |
| ------------ | ----------------- | -------- | ---------------- | ------- | ----- |
| eager | 1.138 | 0.180 | - | - | baseline CUDA forward |
| jit | 0.308 | 0.018 | 0.157 | True | speedup vs eager |
| torch_compile| 0.413 | 0.055 | 1.658 | True | Inductor + Triton works in container |
| onnx | 3.593 | 0.738 | 0.181 | True | ORT runs on CPU |
| tensorrt | 8.198 | 0.191 | 18.039 | True | executed via PyTorch 25.08 container; FP16 build, workspace 256 MB | Artifacts:
- `reports/compilation/transformer_cuda_triton2508.json`
- `reports/compilation/transformer_cuda_triton2508.md`
- `reports/compilation/transformer_cuda_torchtrt_20251003-033530.json`
- `reports/compilation/transformer_cuda_torchtrt_20251003-033530.md` GPU check: `nvidia-smi` (driver 581.29, RTX 4080 Laptop GPU) shows no residual processes after the run.
