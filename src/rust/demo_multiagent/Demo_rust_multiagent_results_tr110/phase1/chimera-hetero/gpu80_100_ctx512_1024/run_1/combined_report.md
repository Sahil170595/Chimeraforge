# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_hetero
- Concurrent Wall Time: 10.90s
- Sequential Estimate: 17.98s
- Speedup: 1.65x
- Efficiency: 82.5% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 100.82 tok/s
- TTFT: 3486.93 ms
- Total Duration: 7085.74 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11434
- Config: num_gpu=100, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.05
- Throughput: 96.55 tok/s
- TTFT: 10278.15 ms
- Total Duration: 10894.71 ms

## Delta (B - A)
- Throughput Δ: -4.27 tok/s
- TTFT Δ: -6791.23 ms (positive = Agent B faster TTFT)
