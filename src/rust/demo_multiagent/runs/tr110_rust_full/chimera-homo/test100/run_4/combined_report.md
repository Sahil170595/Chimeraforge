# Rust Multi-Agent Report - Run 4

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 58.35s
- Sequential Estimate: 115.40s
- Speedup: 1.98x
- Efficiency: 98.9% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=0.6, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 42.43 tok/s
- TTFT: 672.06 ms
- Total Duration: 58321.10 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=512, temp=0.6, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 40.85 tok/s
- TTFT: 663.58 ms
- Total Duration: 57018.52 ms

## Delta (B - A)
- Throughput Δ: -1.58 tok/s
- TTFT Δ: +8.47 ms (positive = Agent B faster TTFT)
