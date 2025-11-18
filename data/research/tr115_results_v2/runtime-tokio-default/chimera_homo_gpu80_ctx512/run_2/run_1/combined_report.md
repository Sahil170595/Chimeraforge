# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 57.00s
- Sequential Estimate: 112.00s
- Speedup: 1.96x
- Efficiency: 98.2% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 43.86 tok/s
- TTFT: 819.29 ms
- Total Duration: 56969.70 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.42 tok/s
- TTFT: 804.58 ms
- Total Duration: 54973.86 ms

## Delta (B - A)
- Throughput Δ: -2.44 tok/s
- TTFT Δ: +14.71 ms (positive = Agent B faster TTFT)
