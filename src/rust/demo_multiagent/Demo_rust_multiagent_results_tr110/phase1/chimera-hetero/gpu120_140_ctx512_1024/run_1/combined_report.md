# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_hetero
- Concurrent Wall Time: 17.62s
- Sequential Estimate: 25.37s
- Speedup: 1.44x
- Efficiency: 72.0% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=120, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 100.58 tok/s
- TTFT: 3386.03 ms
- Total Duration: 7755.95 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11434
- Config: num_gpu=140, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.05
- Throughput: 100.80 tok/s
- TTFT: 10945.63 ms
- Total Duration: 17618.06 ms

## Delta (B - A)
- Throughput Δ: +0.22 tok/s
- TTFT Δ: -7559.60 ms (positive = Agent B faster TTFT)
