# Rust Multi-Agent Report - Run 3

## Scenario
- Type: chimera_hetero
- Concurrent Wall Time: 16.64s
- Sequential Estimate: 26.04s
- Speedup: 1.56x
- Efficiency: 78.2% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=120, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 100.77 tok/s
- TTFT: 12503.91 ms
- Total Duration: 16637.93 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11434
- Config: num_gpu=140, num_ctx=2048, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.05
- Throughput: 100.59 tok/s
- TTFT: 3383.30 ms
- Total Duration: 9397.10 ms

## Delta (B - A)
- Throughput Δ: -0.18 tok/s
- TTFT Δ: +9120.62 ms (positive = Agent B faster TTFT)
