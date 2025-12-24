# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 13.11s
- Sequential Estimate: 23.68s
- Speedup: 1.81x
- Efficiency: 90.3% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.22 tok/s
- TTFT: 705.26 ms
- Total Duration: 10573.61 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 55.40 tok/s
- TTFT: 620.09 ms
- Total Duration: 13105.81 ms

## Delta (B - A)
- Throughput Δ: +14.17 tok/s
- TTFT Δ: +85.17 ms (positive = Agent B faster TTFT)
