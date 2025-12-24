# Rust Multi-Agent Report – Run 3

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 53.92s
- Sequential Estimate: 107.71s
- Speedup: 2.00x
- Efficiency: 99.9% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 38.35 tok/s
- TTFT: 413.45 ms
- Total Duration: 53916.56 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 38.57 tok/s
- TTFT: 521.83 ms
- Total Duration: 53793.88 ms

## Delta (B - A)
- Throughput Δ: +0.22 tok/s
- TTFT Δ: -108.38 ms (positive = Agent B faster TTFT)
