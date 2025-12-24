# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 11.70s
- Sequential Estimate: 21.30s
- Speedup: 1.82x
- Efficiency: 91.0% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=100, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 42.42 tok/s
- TTFT: 653.12 ms
- Total Duration: 9600.73 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=100, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 56.89 tok/s
- TTFT: 574.15 ms
- Total Duration: 11702.09 ms

## Delta (B - A)
- Throughput Δ: +14.47 tok/s
- TTFT Δ: +78.96 ms (positive = Agent B faster TTFT)
