# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_hetero
- Concurrent Wall Time: 10.87s
- Sequential Estimate: 17.36s
- Speedup: 1.60x
- Efficiency: 79.8% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 101.55 tok/s
- TTFT: 6515.80 ms
- Total Duration: 10870.66 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.05
- Throughput: 101.91 tok/s
- TTFT: 211.34 ms
- Total Duration: 6487.23 ms

## Delta (B - A)
- Throughput Δ: +0.37 tok/s
- TTFT Δ: +6304.46 ms (positive = Agent B faster TTFT)
