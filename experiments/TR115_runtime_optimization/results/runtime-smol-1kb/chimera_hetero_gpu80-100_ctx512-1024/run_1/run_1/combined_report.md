# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_hetero
- Concurrent Wall Time: 17.74s
- Sequential Estimate: 32.88s
- Speedup: 1.85x
- Efficiency: 92.7% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 47.47 tok/s
- TTFT: 7241.74 ms
- Total Duration: 15145.51 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=100, num_ctx=1024, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 62.61 tok/s
- TTFT: 7893.36 ms
- Total Duration: 17737.95 ms

## Delta (B - A)
- Throughput Δ: +15.15 tok/s
- TTFT Δ: -651.62 ms (positive = Agent B faster TTFT)
