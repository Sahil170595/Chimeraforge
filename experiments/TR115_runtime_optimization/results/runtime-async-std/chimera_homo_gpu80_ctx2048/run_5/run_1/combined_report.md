# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 10.49s
- Sequential Estimate: 10.49s
- Speedup: 1.00x
- Efficiency: 50.0% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=2048, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 122.46 tok/s
- TTFT: 838.12 ms
- Total Duration: 4396.90 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=2048, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 121.70 tok/s
- TTFT: 612.84 ms
- Total Duration: 6094.96 ms

## Delta (B - A)
- Throughput Δ: -0.77 tok/s
- TTFT Δ: +225.28 ms (positive = Agent B faster TTFT)
