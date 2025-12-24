# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 12.19s
- Sequential Estimate: 22.52s
- Speedup: 1.85x
- Efficiency: 92.4% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=2048, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 42.57 tok/s
- TTFT: 671.34 ms
- Total Duration: 10332.68 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=2048, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 54.84 tok/s
- TTFT: 573.72 ms
- Total Duration: 12189.25 ms

## Delta (B - A)
- Throughput Δ: +12.27 tok/s
- TTFT Δ: +97.62 ms (positive = Agent B faster TTFT)
