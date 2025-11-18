# Rust Multi-Agent Report - Run 2

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 58.61s
- Sequential Estimate: 115.51s
- Speedup: 1.97x
- Efficiency: 98.5% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=1024, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 40.79 tok/s
- TTFT: 688.48 ms
- Total Duration: 56876.96 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=1024, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 42.48 tok/s
- TTFT: 544.70 ms
- Total Duration: 58585.31 ms

## Delta (B - A)
- Throughput Δ: +1.68 tok/s
- TTFT Δ: +143.78 ms (positive = Agent B faster TTFT)
