# Rust Multi-Agent Report - Run 3

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 54.99s
- Sequential Estimate: 108.54s
- Speedup: 1.97x
- Efficiency: 98.7% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=1024, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 42.90 tok/s
- TTFT: 671.02 ms
- Total Duration: 54953.76 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=1024, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.01 tok/s
- TTFT: 669.13 ms
- Total Duration: 53515.17 ms

## Delta (B - A)
- Throughput Δ: -1.89 tok/s
- TTFT Δ: +1.88 ms (positive = Agent B faster TTFT)
