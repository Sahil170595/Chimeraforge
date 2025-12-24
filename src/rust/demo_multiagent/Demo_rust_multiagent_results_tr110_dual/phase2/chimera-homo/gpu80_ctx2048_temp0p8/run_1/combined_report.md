# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 11.43s
- Sequential Estimate: 20.63s
- Speedup: 1.80x
- Efficiency: 90.2% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://127.0.0.1:11434
- Config: num_gpu=80, num_ctx=2048, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 42.25 tok/s
- TTFT: 201.76 ms
- Total Duration: 9199.85 ms

## Agent B (Chimera Agent B)
- Base URL: http://127.0.0.1:11435
- Config: num_gpu=80, num_ctx=2048, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 54.78 tok/s
- TTFT: 347.14 ms
- Total Duration: 11432.62 ms

## Delta (B - A)
- Throughput Δ: +12.53 tok/s
- TTFT Δ: -145.38 ms (positive = Agent B faster TTFT)
