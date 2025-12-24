# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 53.34s
- Sequential Estimate: 105.62s
- Speedup: 1.98x
- Efficiency: 99.0% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=100, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 40.95 tok/s
- TTFT: 1087.42 ms
- Total Duration: 52246.63 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=100, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 42.23 tok/s
- TTFT: 989.91 ms
- Total Duration: 53312.13 ms

## Delta (B - A)
- Throughput Δ: +1.28 tok/s
- TTFT Δ: +97.52 ms (positive = Agent B faster TTFT)
