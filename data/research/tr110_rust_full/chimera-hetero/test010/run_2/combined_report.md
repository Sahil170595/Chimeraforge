# Rust Multi-Agent Report - Run 2

## Scenario
- Type: chimera_hetero
- Concurrent Wall Time: 55.84s
- Sequential Estimate: 109.87s
- Speedup: 1.97x
- Efficiency: 98.4% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=1024, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 40.78 tok/s
- TTFT: 520.75 ms
- Total Duration: 54013.97 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=100, num_ctx=2048, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 43.31 tok/s
- TTFT: 650.61 ms
- Total Duration: 55824.98 ms

## Delta (B - A)
- Throughput Δ: +2.54 tok/s
- TTFT Δ: -129.86 ms (positive = Agent B faster TTFT)
