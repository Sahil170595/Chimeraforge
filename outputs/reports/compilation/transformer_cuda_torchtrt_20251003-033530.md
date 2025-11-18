# Compilation Benchmark Report - Generated: 2025-10-03T03:36:01.545256+00:00
- Model: transformer
- Device: cuda
- DType: torch.float32 | Backend | Success | Compile Time (s) | Mean (ms) | Std (ms) | Min (ms) | Max (ms) | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| eager | yes | 0.0000 | 0.673 | 0.088 | 0.596 | 0.885 | |
| jit | yes | 0.1662 | 0.271 | 0.022 | 0.250 | 0.318 | strict=False; frozen=True; graph_preview=20 lines |
| torch_compile | yes | 1.4436 | 0.388 | 0.085 | 0.311 | 0.544 | backend=inductor; mode=default; fullgraph=False; dynamic=False |
| tensorrt | yes | 18.0392 | 8.198 | 0.191 | 7.965 | 8.553 | enabled_precisions=torch.float16; workspace_size=268435456 |
