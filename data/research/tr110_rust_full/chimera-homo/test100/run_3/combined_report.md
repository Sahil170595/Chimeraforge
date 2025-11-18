# Rust Multi-Agent Report - Run 3

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 54.86s
- Sequential Estimate: 108.51s
- Speedup: 1.98x
- Efficiency: 98.9% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=0.6, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 42.32 tok/s
- TTFT: 503.09 ms
- Total Duration: 54838.37 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=512, temp=0.6, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.18 tok/s
- TTFT: 653.58 ms
- Total Duration: 53620.02 ms

## Delta (B - A)
- Throughput Δ: -1.14 tok/s
- TTFT Δ: -150.49 ms (positive = Agent B faster TTFT)
