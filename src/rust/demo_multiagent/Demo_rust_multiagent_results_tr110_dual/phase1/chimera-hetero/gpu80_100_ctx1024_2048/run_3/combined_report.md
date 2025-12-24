# Rust Multi-Agent Report - Run 3

## Scenario
- Type: chimera_hetero
- Concurrent Wall Time: 12.58s
- Sequential Estimate: 22.20s
- Speedup: 1.76x
- Efficiency: 88.2% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://127.0.0.1:11434
- Config: num_gpu=80, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 41.13 tok/s
- TTFT: 301.40 ms
- Total Duration: 9618.61 ms

## Agent B (Chimera Agent B)
- Base URL: http://127.0.0.1:11435
- Config: num_gpu=100, num_ctx=2048, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.05
- Throughput: 57.35 tok/s
- TTFT: 273.09 ms
- Total Duration: 12576.55 ms

## Delta (B - A)
- Throughput Δ: +16.22 tok/s
- TTFT Δ: +28.31 ms (positive = Agent B faster TTFT)
