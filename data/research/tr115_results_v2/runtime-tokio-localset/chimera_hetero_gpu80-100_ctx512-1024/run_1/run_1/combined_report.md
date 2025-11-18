# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_hetero
- Concurrent Wall Time: 62.30s
- Sequential Estimate: 121.38s
- Speedup: 1.95x
- Efficiency: 97.4% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 45.15 tok/s
- TTFT: 4307.72 ms
- Total Duration: 62259.76 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=100, num_ctx=1024, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.07 tok/s
- TTFT: 4297.57 ms
- Total Duration: 59045.57 ms

## Delta (B - A)
- Throughput Δ: -4.08 tok/s
- TTFT Δ: +10.15 ms (positive = Agent B faster TTFT)
