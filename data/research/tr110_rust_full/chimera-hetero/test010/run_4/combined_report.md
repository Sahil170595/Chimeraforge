# Rust Multi-Agent Report - Run 4

## Scenario
- Type: chimera_hetero
- Concurrent Wall Time: 56.23s
- Sequential Estimate: 111.34s
- Speedup: 1.98x
- Efficiency: 99.0% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=1024, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 42.30 tok/s
- TTFT: 655.48 ms
- Total Duration: 56198.90 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=100, num_ctx=2048, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 40.98 tok/s
- TTFT: 651.75 ms
- Total Duration: 55073.88 ms

## Delta (B - A)
- Throughput Δ: -1.32 tok/s
- TTFT Δ: +3.73 ms (positive = Agent B faster TTFT)
