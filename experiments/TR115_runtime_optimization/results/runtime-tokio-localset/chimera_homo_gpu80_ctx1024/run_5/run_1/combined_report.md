# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 12.04s
- Sequential Estimate: 22.05s
- Speedup: 1.83x
- Efficiency: 91.6% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=1024, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.34 tok/s
- TTFT: 678.00 ms
- Total Duration: 10009.35 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=1024, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 55.35 tok/s
- TTFT: 586.19 ms
- Total Duration: 12041.27 ms

## Delta (B - A)
- Throughput Δ: +14.01 tok/s
- TTFT Δ: +91.82 ms (positive = Agent B faster TTFT)
