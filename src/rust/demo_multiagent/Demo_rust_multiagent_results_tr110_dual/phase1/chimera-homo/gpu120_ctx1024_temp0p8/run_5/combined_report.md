# Rust Multi-Agent Report - Run 5

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 11.55s
- Sequential Estimate: 20.64s
- Speedup: 1.79x
- Efficiency: 89.3% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://127.0.0.1:11434
- Config: num_gpu=120, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 41.33 tok/s
- TTFT: 273.94 ms
- Total Duration: 9090.74 ms

## Agent B (Chimera Agent B)
- Base URL: http://127.0.0.1:11435
- Config: num_gpu=120, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 56.26 tok/s
- TTFT: 313.28 ms
- Total Duration: 11551.76 ms

## Delta (B - A)
- Throughput Δ: +14.93 tok/s
- TTFT Δ: -39.33 ms (positive = Agent B faster TTFT)
