# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_hetero
- Concurrent Wall Time: 13.70s
- Sequential Estimate: 25.10s
- Speedup: 1.83x
- Efficiency: 91.6% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://127.0.0.1:11434
- Config: num_gpu=80, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 41.18 tok/s
- TTFT: 272.04 ms
- Total Duration: 11404.65 ms

## Agent B (Chimera Agent B)
- Base URL: http://127.0.0.1:11435
- Config: num_gpu=100, num_ctx=2048, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.05
- Throughput: 52.60 tok/s
- TTFT: 309.44 ms
- Total Duration: 13694.23 ms

## Delta (B - A)
- Throughput Δ: +11.42 tok/s
- TTFT Δ: -37.40 ms (positive = Agent B faster TTFT)
