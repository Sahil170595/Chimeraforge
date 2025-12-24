# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 12.39s
- Sequential Estimate: 23.49s
- Speedup: 1.90x
- Efficiency: 94.8% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=2048, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 42.65 tok/s
- TTFT: 626.56 ms
- Total Duration: 11103.57 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=2048, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 50.85 tok/s
- TTFT: 548.31 ms
- Total Duration: 12390.56 ms

## Delta (B - A)
- Throughput Δ: +8.20 tok/s
- TTFT Δ: +78.25 ms (positive = Agent B faster TTFT)
