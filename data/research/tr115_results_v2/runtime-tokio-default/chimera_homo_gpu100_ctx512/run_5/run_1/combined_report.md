# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 51.34s
- Sequential Estimate: 100.57s
- Speedup: 1.96x
- Efficiency: 97.9% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=100, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.39 tok/s
- TTFT: 816.81 ms
- Total Duration: 49196.48 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=100, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 44.39 tok/s
- TTFT: 821.98 ms
- Total Duration: 51311.88 ms

## Delta (B - A)
- Throughput Δ: +3.00 tok/s
- TTFT Δ: -5.17 ms (positive = Agent B faster TTFT)
