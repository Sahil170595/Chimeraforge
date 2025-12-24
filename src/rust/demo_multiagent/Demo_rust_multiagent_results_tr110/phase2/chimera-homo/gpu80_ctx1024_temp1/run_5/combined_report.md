# Rust Multi-Agent Report - Run 5

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 10.24s
- Sequential Estimate: 16.59s
- Speedup: 1.62x
- Efficiency: 81.0% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=1024, temp=1, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 100.29 tok/s
- TTFT: 6372.56 ms
- Total Duration: 10242.52 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=1024, temp=1, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 101.66 tok/s
- TTFT: 191.60 ms
- Total Duration: 6346.13 ms

## Delta (B - A)
- Throughput Δ: +1.36 tok/s
- TTFT Δ: +6180.96 ms (positive = Agent B faster TTFT)
