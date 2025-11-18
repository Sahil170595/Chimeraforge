# Compilation Benchmark Report - Generated: 2025-10-03T03:19:06.069710+00:00
- Model: transformer
- Device: cuda
- DType: torch.float32 | Backend | Success | Compile Time (s) | Mean (ms) | Std (ms) | Min (ms) | Max (ms) | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| eager | yes | 0.0000 | 0.685 | 0.060 | 0.630 | 0.800 | |
| jit | yes | 0.1202 | 0.347 | 0.040 | 0.285 | 0.403 | strict=False; frozen=True; graph_preview=20 lines |
| torch_compile | yes | 1.5708 | 0.481 | 0.089 | 0.401 | 0.645 | backend=inductor; mode=default; fullgraph=False; dynamic=False |
| onnx | yes | 0.2337 | 4.095 | 0.105 | 3.922 | 4.214 | onnx_path=/tmp/chimera_onnx__p4itfkf/model.onnx; opset=17; providers=CPUExecutionProvider; session_type=onnxruntime |
| tensorrt | no | 0.0000 | 0.000 | 0.000 | 0.000 | 0.000 | error=torch_tensorrt is not installed |
