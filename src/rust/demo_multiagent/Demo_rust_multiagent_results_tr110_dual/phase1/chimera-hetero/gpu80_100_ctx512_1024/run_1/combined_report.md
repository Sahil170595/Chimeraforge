# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_hetero
- Concurrent Wall Time: 20.19s
- Sequential Estimate: 38.64s
- Speedup: 1.91x
- Efficiency: 95.7% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://127.0.0.1:11434
- Config: num_gpu=80, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 41.16 tok/s
- TTFT: 7862.58 ms
- Total Duration: 18449.42 ms

## Agent B (Chimera Agent B)
- Base URL: http://127.0.0.1:11435
- Config: num_gpu=100, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.05
- Throughput: 50.84 tok/s
- TTFT: 7859.75 ms
- Total Duration: 20187.99 ms

## Delta (B - A)
- Throughput Δ: +9.69 tok/s
- TTFT Δ: +2.83 ms (positive = Agent B faster TTFT)
