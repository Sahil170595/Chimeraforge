# Compilation Benchmark Report - Generated: 2025-10-03T02:43:56.023041+00:00
- Model: transformer
- Device: cuda
- DType: torch.float32 | Backend | Success | Compile Time (s) | Mean (ms) | Std (ms) | Min (ms) | Max (ms) | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| eager | yes | 0.0000 | 1.695 | 0.367 | 1.355 | 2.357 | |
| jit | yes | 0.1552 | 0.321 | 0.022 | 0.282 | 0.347 | strict=False; frozen=True; graph_preview=20 lines |
| torch_compile | yes | 1.7326 | 0.587 | 0.100 | 0.473 | 0.760 | backend=inductor; mode=default; fullgraph=False; dynamic=False |
| onnx | yes | 0.2157 | 3.758 | 0.345 | 3.344 | 4.315 | onnx_path=/tmp/chimera_onnx_3pk3j8cw/model.onnx; opset=17; providers=CPUExecutionProvider; session_type=onnxruntime |
| tensorrt | no | 0.0000 | 0.000 | 0.000 | 0.000 | 0.000 | error=torch_tensorrt is not installed |
