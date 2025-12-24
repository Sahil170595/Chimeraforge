# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_hetero
- Concurrent Wall Time: 13.03s
- Sequential Estimate: 24.46s
- Speedup: 1.88x
- Efficiency: 93.8% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://127.0.0.1:11434
- Config: num_gpu=120, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 40.95 tok/s
- TTFT: 288.12 ms
- Total Duration: 11427.72 ms

## Agent B (Chimera Agent B)
- Base URL: http://127.0.0.1:11435
- Config: num_gpu=140, num_ctx=2048, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.05
- Throughput: 49.54 tok/s
- TTFT: 315.02 ms
- Total Duration: 13029.24 ms

## Delta (B - A)
- Throughput Δ: +8.59 tok/s
- TTFT Δ: -26.90 ms (positive = Agent B faster TTFT)
