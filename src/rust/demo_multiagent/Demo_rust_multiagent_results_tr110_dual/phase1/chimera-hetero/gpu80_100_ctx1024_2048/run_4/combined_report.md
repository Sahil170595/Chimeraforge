# Rust Multi-Agent Report - Run 4

## Scenario
- Type: chimera_hetero
- Concurrent Wall Time: 13.51s
- Sequential Estimate: 24.76s
- Speedup: 1.83x
- Efficiency: 91.6% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://127.0.0.1:11434
- Config: num_gpu=80, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 41.02 tok/s
- TTFT: 309.26 ms
- Total Duration: 11250.02 ms

## Agent B (Chimera Agent B)
- Base URL: http://127.0.0.1:11435
- Config: num_gpu=100, num_ctx=2048, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.05
- Throughput: 52.68 tok/s
- TTFT: 309.18 ms
- Total Duration: 13507.08 ms

## Delta (B - A)
- Throughput Δ: +11.66 tok/s
- TTFT Δ: +0.08 ms (positive = Agent B faster TTFT)
