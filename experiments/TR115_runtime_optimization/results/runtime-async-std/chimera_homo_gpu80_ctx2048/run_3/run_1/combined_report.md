# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 9.98s
- Sequential Estimate: 9.98s
- Speedup: 1.00x
- Efficiency: 50.0% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=2048, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 123.06 tok/s
- TTFT: 733.06 ms
- Total Duration: 3802.40 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=2048, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 121.74 tok/s
- TTFT: 612.14 ms
- Total Duration: 6181.25 ms

## Delta (B - A)
- Throughput Δ: -1.33 tok/s
- TTFT Δ: +120.92 ms (positive = Agent B faster TTFT)
