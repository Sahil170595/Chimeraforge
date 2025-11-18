# Compilation Benchmark Report - Generated: 2025-10-02T21:09:22.605748+00:00
- Model: transformer
- Device: cpu
- DType: torch.float32 | Backend | Success | Compile Time (s) | Mean (ms) | Std (ms) | Min (ms) | Max (ms) | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| eager | yes | 0.0000 | 24.723 | 2.248 | 21.698 | 30.158 | |
| jit | yes | 0.1753 | 4.859 | 0.585 | 4.242 | 5.718 | strict=False; frozen=True; graph_preview=20 lines |
| torch_compile | yes | 0.8980 | 5.665 | 0.316 | 5.114 | 6.199 | backend=inductor; mode=default; fullgraph=False; dynamic=False |
| onnx | yes | 0.3130 | 2.837 | 0.070 | 2.743 | 2.995 | onnx_path=C:\Users\sahil\AppData\Local\Temp\chimera_onnx_wj_1y_ig\model.onnx; opset=17; providers=CPUExecutionProvider; session_type=onnxruntime |
