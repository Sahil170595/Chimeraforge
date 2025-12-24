# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 50.64s
- Sequential Estimate: 99.29s
- Speedup: 1.96x
- Efficiency: 98.0% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=100, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 46.04 tok/s
- TTFT: 773.32 ms
- Total Duration: 50591.06 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=100, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 42.98 tok/s
- TTFT: 777.31 ms
- Total Duration: 48615.56 ms

## Delta (B - A)
- Throughput Δ: -3.06 tok/s
- TTFT Δ: -3.99 ms (positive = Agent B faster TTFT)
