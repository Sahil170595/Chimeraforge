# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 58.06s
- Sequential Estimate: 115.20s
- Speedup: 1.98x
- Efficiency: 99.2% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 42.48 tok/s
- TTFT: 587.16 ms
- Total Duration: 58021.62 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=512, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 40.99 tok/s
- TTFT: 845.50 ms
- Total Duration: 57112.34 ms

## Delta (B - A)
- Throughput Δ: -1.50 tok/s
- TTFT Δ: -258.34 ms (positive = Agent B faster TTFT)
