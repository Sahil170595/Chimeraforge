# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_hetero
- Concurrent Wall Time: 16.44s
- Sequential Estimate: 25.85s
- Speedup: 1.57x
- Efficiency: 78.6% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=60, num_ctx=512, temp=0.6, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 102.54 tok/s
- TTFT: 12607.39 ms
- Total Duration: 16435.90 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11434
- Config: num_gpu=120, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.05
- Throughput: 101.54 tok/s
- TTFT: 3391.47 ms
- Total Duration: 9411.59 ms

## Delta (B - A)
- Throughput Δ: -1.00 tok/s
- TTFT Δ: +9215.91 ms (positive = Agent B faster TTFT)
