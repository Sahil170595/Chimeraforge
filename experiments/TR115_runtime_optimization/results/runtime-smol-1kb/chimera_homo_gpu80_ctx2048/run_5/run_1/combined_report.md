# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 12.41s
- Sequential Estimate: 23.55s
- Speedup: 1.90x
- Efficiency: 94.8% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=2048, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 42.58 tok/s
- TTFT: 947.39 ms
- Total Duration: 11134.87 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=2048, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 50.97 tok/s
- TTFT: 665.80 ms
- Total Duration: 12413.19 ms

## Delta (B - A)
- Throughput Δ: +8.39 tok/s
- TTFT Δ: +281.59 ms (positive = Agent B faster TTFT)
