# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 13.12s
- Sequential Estimate: 24.99s
- Speedup: 1.90x
- Efficiency: 95.2% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 42.34 tok/s
- TTFT: 728.94 ms
- Total Duration: 11862.33 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 50.80 tok/s
- TTFT: 538.29 ms
- Total Duration: 13123.92 ms

## Delta (B - A)
- Throughput Δ: +8.46 tok/s
- TTFT Δ: +190.65 ms (positive = Agent B faster TTFT)
