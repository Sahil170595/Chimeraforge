# Compilation Benchmark Report - Generated: 2025-10-02T21:21:56.014430+00:00
- Model: transformer
- Device: cuda
- DType: torch.float32 | Backend | Success | Compile Time (s) | Mean (ms) | Std (ms) | Min (ms) | Max (ms) | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| eager | yes | 0.0000 | 0.796 | 0.032 | 0.757 | 0.845 | |
| jit | yes | 0.1602 | 0.809 | 0.043 | 0.744 | 0.884 | strict=False; frozen=True; graph_preview=20 lines |
| torch_compile | no | 0.0000 | 0.000 | 0.000 | 0.000 | 0.000 | error=Cannot find a working triton installation. Either the package is not installed or it is too old. More information on installing Triton can be found at: https://github.com/triton-lang/triton Set TORCHDYNAMO_VERBOSE=1 for the internal stack trace (please do this especially if you're reporting a bug to PyTorch). For even more developer context, set TORCH_LOGS="+dynamo" |
| onnx | yes | 0.2346 | 3.109 | 0.281 | 2.708 | 3.581 | onnx_path=C:\Users\sahil\AppData\Local\Temp\chimera_onnx_szuyfbwu\model.onnx; opset=17; providers=CPUExecutionProvider; session_type=onnxruntime |
| tensorrt | yes | 21.2289 | 1.182 | 0.152 | 1.100 | 1.627 | enabled_precisions=torch.float16; workspace_size=268435456 |
