# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_hetero
- Concurrent Wall Time: 12.98s
- Sequential Estimate: 24.05s
- Speedup: 1.85x
- Efficiency: 92.7% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 42.55 tok/s
- TTFT: 643.58 ms
- Total Duration: 11073.24 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=100, num_ctx=1024, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 54.11 tok/s
- TTFT: 586.59 ms
- Total Duration: 12974.37 ms

## Delta (B - A)
- Throughput Δ: +11.56 tok/s
- TTFT Δ: +56.99 ms (positive = Agent B faster TTFT)
