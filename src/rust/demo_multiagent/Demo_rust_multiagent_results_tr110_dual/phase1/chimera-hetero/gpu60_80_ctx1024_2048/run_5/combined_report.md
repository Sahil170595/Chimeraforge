# Rust Multi-Agent Report - Run 5

## Scenario
- Type: chimera_hetero
- Concurrent Wall Time: 13.32s
- Sequential Estimate: 24.49s
- Speedup: 1.84x
- Efficiency: 92.0% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://127.0.0.1:11434
- Config: num_gpu=60, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 40.83 tok/s
- TTFT: 281.54 ms
- Total Duration: 11175.47 ms

## Agent B (Chimera Agent B)
- Base URL: http://127.0.0.1:11435
- Config: num_gpu=80, num_ctx=2048, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.05
- Throughput: 52.01 tok/s
- TTFT: 299.45 ms
- Total Duration: 13319.07 ms

## Delta (B - A)
- Throughput Δ: +11.18 tok/s
- TTFT Δ: -17.90 ms (positive = Agent B faster TTFT)
