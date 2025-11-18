# Rust Multi-Agent Report - Run 5

## Scenario
- Type: chimera_hetero
- Concurrent Wall Time: 58.61s
- Sequential Estimate: 116.99s
- Speedup: 2.00x
- Efficiency: 99.8% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.11 tok/s
- TTFT: 660.83 ms
- Total Duration: 58347.25 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=1024, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.14 tok/s
- TTFT: 587.71 ms
- Total Duration: 58582.65 ms

## Delta (B - A)
- Throughput Δ: +0.03 tok/s
- TTFT Δ: +73.12 ms (positive = Agent B faster TTFT)
