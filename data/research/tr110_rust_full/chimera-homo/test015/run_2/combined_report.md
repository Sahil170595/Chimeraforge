# Rust Multi-Agent Report - Run 2

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 56.41s
- Sequential Estimate: 110.94s
- Speedup: 1.97x
- Efficiency: 98.3% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 43.41 tok/s
- TTFT: 654.73 ms
- Total Duration: 56373.73 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=512, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.12 tok/s
- TTFT: 654.61 ms
- Total Duration: 54495.97 ms

## Delta (B - A)
- Throughput Δ: -2.29 tok/s
- TTFT Δ: +0.12 ms (positive = Agent B faster TTFT)
