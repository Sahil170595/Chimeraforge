# Rust Multi-Agent Report - Run 5

## Scenario
- Type: chimera_hetero
- Concurrent Wall Time: 12.01s
- Sequential Estimate: 21.01s
- Speedup: 1.75x
- Efficiency: 87.5% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://127.0.0.1:11434
- Config: num_gpu=60, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 41.16 tok/s
- TTFT: 302.51 ms
- Total Duration: 9002.17 ms

## Agent B (Chimera Agent B)
- Base URL: http://127.0.0.1:11435
- Config: num_gpu=80, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.05
- Throughput: 58.71 tok/s
- TTFT: 333.55 ms
- Total Duration: 12010.40 ms

## Delta (B - A)
- Throughput Δ: +17.55 tok/s
- TTFT Δ: -31.04 ms (positive = Agent B faster TTFT)
