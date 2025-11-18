# Rust Multi-Agent Report - Run 3

## Scenario
- Type: chimera_hetero
- Concurrent Wall Time: 52.48s
- Sequential Estimate: 103.73s
- Speedup: 1.98x
- Efficiency: 98.8% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=120, num_ctx=512, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 42.56 tok/s
- TTFT: 662.12 ms
- Total Duration: 52447.65 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=140, num_ctx=1024, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 40.69 tok/s
- TTFT: 555.97 ms
- Total Duration: 51221.67 ms

## Delta (B - A)
- Throughput Δ: -1.87 tok/s
- TTFT Δ: +106.15 ms (positive = Agent B faster TTFT)
