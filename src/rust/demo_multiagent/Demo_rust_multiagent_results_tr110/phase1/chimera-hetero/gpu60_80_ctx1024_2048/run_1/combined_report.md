# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_hetero
- Concurrent Wall Time: 17.42s
- Sequential Estimate: 28.00s
- Speedup: 1.61x
- Efficiency: 80.4% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=60, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 100.84 tok/s
- TTFT: 13735.94 ms
- Total Duration: 17418.28 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=2048, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.05
- Throughput: 99.67 tok/s
- TTFT: 3347.19 ms
- Total Duration: 10586.55 ms

## Delta (B - A)
- Throughput Δ: -1.17 tok/s
- TTFT Δ: +10388.75 ms (positive = Agent B faster TTFT)
