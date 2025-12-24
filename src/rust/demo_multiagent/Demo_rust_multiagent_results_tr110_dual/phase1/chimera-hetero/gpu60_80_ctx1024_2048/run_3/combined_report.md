# Rust Multi-Agent Report - Run 3

## Scenario
- Type: chimera_hetero
- Concurrent Wall Time: 12.27s
- Sequential Estimate: 22.30s
- Speedup: 1.82x
- Efficiency: 90.9% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://127.0.0.1:11434
- Config: num_gpu=60, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 41.02 tok/s
- TTFT: 263.87 ms
- Total Duration: 10028.41 ms

## Agent B (Chimera Agent B)
- Base URL: http://127.0.0.1:11435
- Config: num_gpu=80, num_ctx=2048, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.05
- Throughput: 53.84 tok/s
- TTFT: 289.40 ms
- Total Duration: 12271.30 ms

## Delta (B - A)
- Throughput Δ: +12.81 tok/s
- TTFT Δ: -25.53 ms (positive = Agent B faster TTFT)
