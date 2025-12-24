# Rust Multi-Agent Report - Run 5

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 10.61s
- Sequential Estimate: 14.19s
- Speedup: 1.34x
- Efficiency: 66.9% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=2048, temp=0.6, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 101.74 tok/s
- TTFT: 206.04 ms
- Total Duration: 3577.98 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=2048, temp=0.6, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 100.70 tok/s
- TTFT: 3609.23 ms
- Total Duration: 10614.63 ms

## Delta (B - A)
- Throughput Δ: -1.03 tok/s
- TTFT Δ: -3403.18 ms (positive = Agent B faster TTFT)
