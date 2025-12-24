# Rust Multi-Agent Report - Run 2

## Scenario
- Type: chimera_hetero
- Concurrent Wall Time: 14.17s
- Sequential Estimate: 20.64s
- Speedup: 1.46x
- Efficiency: 72.8% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=60, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 100.36 tok/s
- TTFT: 9606.15 ms
- Total Duration: 14165.60 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.05
- Throughput: 101.34 tok/s
- TTFT: 201.76 ms
- Total Duration: 6470.52 ms

## Delta (B - A)
- Throughput Δ: +0.98 tok/s
- TTFT Δ: +9404.39 ms (positive = Agent B faster TTFT)
