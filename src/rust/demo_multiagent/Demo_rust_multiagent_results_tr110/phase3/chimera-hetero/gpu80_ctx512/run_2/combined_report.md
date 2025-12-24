# Rust Multi-Agent Report - Run 2

## Scenario
- Type: chimera_hetero
- Concurrent Wall Time: 10.20s
- Sequential Estimate: 14.54s
- Speedup: 1.42x
- Efficiency: 71.2% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 101.28 tok/s
- TTFT: 174.95 ms
- Total Duration: 4333.91 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.05
- Throughput: 101.85 tok/s
- TTFT: 4364.18 ms
- Total Duration: 10201.85 ms

## Delta (B - A)
- Throughput Δ: +0.57 tok/s
- TTFT Δ: -4189.23 ms (positive = Agent B faster TTFT)
