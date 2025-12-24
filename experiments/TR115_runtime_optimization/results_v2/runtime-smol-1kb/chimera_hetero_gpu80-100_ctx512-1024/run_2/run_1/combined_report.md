# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_hetero
- Concurrent Wall Time: 44.93s
- Sequential Estimate: 85.76s
- Speedup: 1.91x
- Efficiency: 95.4% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 49.25 tok/s
- TTFT: 975.95 ms
- Total Duration: 44893.12 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=100, num_ctx=1024, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 40.91 tok/s
- TTFT: 884.13 ms
- Total Duration: 40791.38 ms

## Delta (B - A)
- Throughput Δ: -8.34 tok/s
- TTFT Δ: +91.83 ms (positive = Agent B faster TTFT)
