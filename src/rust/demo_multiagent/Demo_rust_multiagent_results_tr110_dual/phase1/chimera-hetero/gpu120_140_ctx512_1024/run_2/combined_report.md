# Rust Multi-Agent Report - Run 2

## Scenario
- Type: chimera_hetero
- Concurrent Wall Time: 12.36s
- Sequential Estimate: 22.76s
- Speedup: 1.84x
- Efficiency: 92.0% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://127.0.0.1:11434
- Config: num_gpu=120, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 41.29 tok/s
- TTFT: 265.65 ms
- Total Duration: 10398.08 ms

## Agent B (Chimera Agent B)
- Base URL: http://127.0.0.1:11435
- Config: num_gpu=140, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.05
- Throughput: 52.13 tok/s
- TTFT: 321.37 ms
- Total Duration: 12363.15 ms

## Delta (B - A)
- Throughput Δ: +10.84 tok/s
- TTFT Δ: -55.72 ms (positive = Agent B faster TTFT)
