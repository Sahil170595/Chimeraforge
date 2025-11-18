# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 33.71s
- Sequential Estimate: 33.70s
- Speedup: 1.00x
- Efficiency: 50.0% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=1024, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 139.22 tok/s
- TTFT: 591.42 ms
- Total Duration: 10443.31 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=1024, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 108.26 tok/s
- TTFT: 604.02 ms
- Total Duration: 23189.45 ms

## Delta (B - A)
- Throughput Δ: -30.96 tok/s
- TTFT Δ: -12.60 ms (positive = Agent B faster TTFT)
