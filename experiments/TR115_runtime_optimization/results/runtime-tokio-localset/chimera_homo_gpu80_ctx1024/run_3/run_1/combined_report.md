# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 13.14s
- Sequential Estimate: 23.74s
- Speedup: 1.81x
- Efficiency: 90.4% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=1024, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 40.71 tok/s
- TTFT: 710.77 ms
- Total Duration: 10604.26 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=1024, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 54.89 tok/s
- TTFT: 604.96 ms
- Total Duration: 13138.64 ms

## Delta (B - A)
- Throughput Δ: +14.18 tok/s
- TTFT Δ: +105.81 ms (positive = Agent B faster TTFT)
