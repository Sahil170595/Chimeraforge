# Rust Multi-Agent Report - Run 4

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 12.46s
- Sequential Estimate: 22.62s
- Speedup: 1.82x
- Efficiency: 90.8% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://127.0.0.1:11434
- Config: num_gpu=60, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 41.28 tok/s
- TTFT: 273.78 ms
- Total Duration: 10163.88 ms

## Agent B (Chimera Agent B)
- Base URL: http://127.0.0.1:11435
- Config: num_gpu=60, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 54.07 tok/s
- TTFT: 308.50 ms
- Total Duration: 12458.13 ms

## Delta (B - A)
- Throughput Δ: +12.80 tok/s
- TTFT Δ: -34.72 ms (positive = Agent B faster TTFT)
