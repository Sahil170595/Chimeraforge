# Rust Multi-Agent Report - Run 4

## Scenario
- Type: chimera_hetero
- Concurrent Wall Time: 13.05s
- Sequential Estimate: 19.27s
- Speedup: 1.48x
- Efficiency: 73.8% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=120, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 100.79 tok/s
- TTFT: 9417.76 ms
- Total Duration: 13047.96 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11434
- Config: num_gpu=140, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.05
- Throughput: 101.67 tok/s
- TTFT: 169.16 ms
- Total Duration: 6221.33 ms

## Delta (B - A)
- Throughput Δ: +0.88 tok/s
- TTFT Δ: +9248.60 ms (positive = Agent B faster TTFT)
