# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 16.80s
- Sequential Estimate: 31.00s
- Speedup: 1.85x
- Efficiency: 92.3% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=100, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 43.92 tok/s
- TTFT: 6319.90 ms
- Total Duration: 14203.50 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=100, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 61.72 tok/s
- TTFT: 6520.42 ms
- Total Duration: 16799.48 ms

## Delta (B - A)
- Throughput Δ: +17.80 tok/s
- TTFT Δ: -200.53 ms (positive = Agent B faster TTFT)
