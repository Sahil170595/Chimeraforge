# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 11.97s
- Sequential Estimate: 21.58s
- Speedup: 1.80x
- Efficiency: 90.1% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=2048, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 42.75 tok/s
- TTFT: 922.77 ms
- Total Duration: 9603.02 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=2048, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 58.89 tok/s
- TTFT: 670.48 ms
- Total Duration: 11973.65 ms

## Delta (B - A)
- Throughput Δ: +16.14 tok/s
- TTFT Δ: +252.29 ms (positive = Agent B faster TTFT)
