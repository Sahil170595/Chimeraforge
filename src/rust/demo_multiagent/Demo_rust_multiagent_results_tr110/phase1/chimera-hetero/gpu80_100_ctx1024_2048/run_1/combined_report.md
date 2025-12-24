# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_hetero
- Concurrent Wall Time: 16.27s
- Sequential Estimate: 23.60s
- Speedup: 1.45x
- Efficiency: 72.5% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 100.33 tok/s
- TTFT: 3397.16 ms
- Total Duration: 7331.75 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11434
- Config: num_gpu=100, num_ctx=2048, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.05
- Throughput: 101.09 tok/s
- TTFT: 10518.58 ms
- Total Duration: 16272.16 ms

## Delta (B - A)
- Throughput Δ: +0.76 tok/s
- TTFT Δ: -7121.42 ms (positive = Agent B faster TTFT)
