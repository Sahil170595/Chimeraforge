# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 11.39s
- Sequential Estimate: 20.52s
- Speedup: 1.80x
- Efficiency: 90.1% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=2048, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 42.67 tok/s
- TTFT: 850.33 ms
- Total Duration: 9129.09 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=2048, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 58.42 tok/s
- TTFT: 748.63 ms
- Total Duration: 11387.85 ms

## Delta (B - A)
- Throughput Δ: +15.75 tok/s
- TTFT Δ: +101.70 ms (positive = Agent B faster TTFT)
