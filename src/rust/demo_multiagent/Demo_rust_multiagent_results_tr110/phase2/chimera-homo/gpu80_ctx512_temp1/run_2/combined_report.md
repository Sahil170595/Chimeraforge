# Rust Multi-Agent Report - Run 2

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 10.19s
- Sequential Estimate: 13.74s
- Speedup: 1.35x
- Efficiency: 67.4% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 101.11 tok/s
- TTFT: 202.61 ms
- Total Duration: 3547.59 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 100.18 tok/s
- TTFT: 3577.57 ms
- Total Duration: 10191.42 ms

## Delta (B - A)
- Throughput Δ: -0.94 tok/s
- TTFT Δ: -3374.96 ms (positive = Agent B faster TTFT)
