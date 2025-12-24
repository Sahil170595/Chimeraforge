# Rust Multi-Agent Report - Run 2

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 12.82s
- Sequential Estimate: 24.01s
- Speedup: 1.87x
- Efficiency: 93.6% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://127.0.0.1:11434
- Config: num_gpu=60, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 41.13 tok/s
- TTFT: 300.67 ms
- Total Duration: 11190.48 ms

## Agent B (Chimera Agent B)
- Base URL: http://127.0.0.1:11435
- Config: num_gpu=60, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 49.87 tok/s
- TTFT: 280.55 ms
- Total Duration: 12820.55 ms

## Delta (B - A)
- Throughput Δ: +8.73 tok/s
- TTFT Δ: +20.12 ms (positive = Agent B faster TTFT)
