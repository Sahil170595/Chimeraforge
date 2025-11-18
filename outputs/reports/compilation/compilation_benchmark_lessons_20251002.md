# Compilation Benchmark Lessons - 2025-10-02 ## Context
- Ran `scripts/compilation/run_compilation_benchmarks.py` across CPU and CUDA for three template models (`mlp`, `conv`, `transformer`).
- Settings: 10 timed runs, 3 warmups, backends `eager`, `jit`, `torch_compile`, `onnx`, plus `tensorrt` on CUDA runs.
- Artifacts now include both CPU and CUDA variants: - CPU: `mlp_bench_20251002-165750.{json,md}`, `conv_bench_20251002-170837.{json,md}`, `transformer_bench_20251002-170914.{json,md}`. - CUDA: `mlp_cuda_bench_20251002-171845.{json,md}`, `conv_cuda_bench_20251002-172037.{json,md}`, `transformer_cuda_bench_20251002-172126.{json,md}`.
- Environment setup: - CPU runs: Visual Studio `vcvars64.bat` to expose `cl.exe` for Inductor. - CUDA runs: same VS setup + newly installed `torch-tensorrt==2.8.0` (+ bundled TensorRT 10.12 libraries).
- Triton kernels are not available on Windows, so GPU `torch.compile` still reports the standard Triton-missing error; CPU Inductor succeeds.
- Hugging Face checkpoints remain out-of-scope (local PyTorch templates only). ## CPU Model Configurations
| Model | Shape / Notes |
| ----- | -------------- |
| `mlp` | Batch 4 x 256 features, hidden width 512.
| `conv` | Batch 4 x 3x128x128 image stack (two conv blocks + 1x1 head).
| `transformer` | Batch 2 x 128 tokens x 256 dim, 2 encoder layers, 4 attention heads. ### CPU Performance Snapshot
| Model | Backend | Mean Latency (ms) | Compile Time (s) | Notes |
| ----- | ------- | ---------------- | ---------------- | ----- |
| `mlp` | eager | 0.493 | - | Baseline FP32 forward |
| | jit | 0.635 | 0.0576 | Tracing overhead; minimal gain |
| | torch_compile | 0.869 | 6.4231 | Inductor works; compile dominates runtime |
| | onnx | 0.051 | 0.0865 | Fastest CPU backend |
| `conv` | eager | 3.812 | - | Baseline |
| | jit | 3.782 | 0.0988 | Minor speedup |
| | torch_compile | 4.103 | 12.9431 | Compilation cost outweighs benefit |
| | onnx | 0.693 | 0.1313 | ~5.5x faster than eager |
| `transformer` | eager | 24.723 | - | Baseline |
| | jit | 4.859 | 0.1753 | ~5x faster |
| | torch_compile | 5.665 | 0.8980 | Inductor close to JIT with sub-second compile |
| | onnx | 2.837 | 0.3130 | Best CPU latency | ## CUDA Performance Snapshot
| Model | Backend | Mean Latency (ms) | Compile Time (s) | Notes |
| ----- | ------- | ---------------- | ---------------- | ----- |
| `mlp` | eager | 0.241 | - | Baseline CUDA forward |
| | jit | 0.214 | 0.0503 | Slight gain |
| | torch_compile | - | - | **Failed:** Triton not available on Windows |
| | onnx | 0.0469 | 0.0600 | ONNX export executes on CPU |
| | tensorrt | 0.404 | 4.2948 | TensorRT engine builds successfully |
| `conv` | eager | 0.154 | - | Baseline CUDA |
| | jit | 0.162 | 0.0699 | Similar performance |
| | torch_compile | - | - | **Failed:** Triton missing |
| | onnx | 0.774 | 0.1425 | Runs via CPU session |
| | tensorrt | 0.431 | 17.1626 | Engine build heavy; runtime good |
| `transformer` | eager | 0.796 | - | Baseline CUDA |
| | jit | 0.809 | 0.1602 | Comparable |
| | torch_compile | - | - | **Failed:** Triton missing |
| | onnx | 3.109 | 0.2346 | CPU session |
| | tensorrt | 1.182 | 21.2289 | TensorRT runtime solid once built | ## Automation Helpers
- `scripts/compilation/run_all_benchmarks.py` - wraps `vcvars64.bat` and runs the CPU/GPU suites in one go (for example: `python scripts/compilation/run_all_benchmarks.py --devices cpu cuda`).
- `scripts/compilation/visualize_benchmarks.py` - converts every JSON artifact under `reports/compilation/` into summary plots saved in `reports/compilation/figures/`. ## Lessons Learned
1. **MSVC unlocks CPU Inductor** - invoking `vcvars64.bat` (or a Developer shell) enables `torch.compile` on CPU for all templates.
2. **ONNX Runtime dominates CPU latency** - across all models ORT provides 5-10x lower latency versus eager, with modest export times.
3. **Compilation cost vs. model size** - small MLP/CNN workloads don't benefit from Inductor yet; compilation time dwarfs execution.
4. **CUDA Inductor blocked by Triton on Windows** - GPU `torch.compile` currently fails because no Triton wheels exist for Windows; track upstream support or run GPU Inductor on Linux.
5. **Torch-TensorRT needs the PyTorch base container** - the trtllm image conflicts with torch-tensorrt; `scripts/compilation/run_tensorrt_docker.py` runs inside `nvcr.io/nvidia/pytorch:25.08-py3` where Torch 2.8.0 and TensorRT 10.13 stay in sync.
6. **Script covers attention-style benchmarks** - the new transformer preset (tunable seq len, dim, heads, layers) gives a decent proxy for LLM workloads without pulling HF yet.
7. **Next frontier: real model integration** - once Hugging Face checkpoints are available locally we can reuse the same pipeline to profile production weights. ## Next Steps
- Add automated container runs via `python scripts/compilation/run_tensorrt_docker.py` for Torch-TensorRT benchmarks.
- Wrap the `vcvars64.bat` invocation (and optional TensorRT environment setup) inside helper scripts so CI/users don't need manual steps.
- Move GPU Inductor experiments to a Linux machine if Triton becomes a hard requirement.
- Add automated comparison notebooks/plots for the new JSON outputs.
- Revisit once Hugging Face models are local to produce production-grade reports. 