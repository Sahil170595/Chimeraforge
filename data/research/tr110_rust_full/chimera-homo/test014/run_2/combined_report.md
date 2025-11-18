# Rust Multi-Agent Report - Run 2

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 56.15s
- Sequential Estimate: 109.93s
- Speedup: 1.96x
- Efficiency: 97.9% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=60, num_ctx=1024, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.16 tok/s
- TTFT: 655.79 ms
- Total Duration: 53746.75 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=60, num_ctx=1024, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 44.18 tok/s
- TTFT: 653.39 ms
- Total Duration: 56118.86 ms

## Delta (B - A)
- Throughput Δ: +3.02 tok/s
- TTFT Δ: +2.41 ms (positive = Agent B faster TTFT)
