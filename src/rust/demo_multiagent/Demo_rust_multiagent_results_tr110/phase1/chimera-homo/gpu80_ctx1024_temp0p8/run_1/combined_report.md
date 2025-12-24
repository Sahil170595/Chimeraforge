# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 10.48s
- Sequential Estimate: 17.31s
- Speedup: 1.65x
- Efficiency: 82.6% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 100.39 tok/s
- TTFT: 6859.28 ms
- Total Duration: 10476.62 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 99.70 tok/s
- TTFT: 226.46 ms
- Total Duration: 6831.46 ms

## Delta (B - A)
- Throughput Δ: -0.69 tok/s
- TTFT Δ: +6632.82 ms (positive = Agent B faster TTFT)
