# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 11.72s
- Sequential Estimate: 21.31s
- Speedup: 1.82x
- Efficiency: 90.9% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=1024, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 42.60 tok/s
- TTFT: 642.61 ms
- Total Duration: 9589.61 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=1024, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 56.90 tok/s
- TTFT: 572.38 ms
- Total Duration: 11721.17 ms

## Delta (B - A)
- Throughput Δ: +14.30 tok/s
- TTFT Δ: +70.23 ms (positive = Agent B faster TTFT)
