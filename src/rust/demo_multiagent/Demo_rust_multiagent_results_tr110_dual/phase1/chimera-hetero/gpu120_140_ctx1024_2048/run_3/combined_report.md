# Rust Multi-Agent Report - Run 3

## Scenario
- Type: chimera_hetero
- Concurrent Wall Time: 12.77s
- Sequential Estimate: 23.22s
- Speedup: 1.82x
- Efficiency: 90.9% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://127.0.0.1:11434
- Config: num_gpu=120, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 41.13 tok/s
- TTFT: 250.89 ms
- Total Duration: 10447.65 ms

## Agent B (Chimera Agent B)
- Base URL: http://127.0.0.1:11435
- Config: num_gpu=140, num_ctx=2048, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.05
- Throughput: 53.57 tok/s
- TTFT: 299.09 ms
- Total Duration: 12770.36 ms

## Delta (B - A)
- Throughput Δ: +12.45 tok/s
- TTFT Δ: -48.19 ms (positive = Agent B faster TTFT)
