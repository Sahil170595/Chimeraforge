# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 5.13s
- Sequential Estimate: 5.13s
- Speedup: 1.00x
- Efficiency: 50.0% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=100, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 122.35 tok/s
- TTFT: 848.44 ms
- Total Duration: 3903.85 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=100, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 124.97 tok/s
- TTFT: 614.82 ms
- Total Duration: 1228.93 ms

## Delta (B - A)
- Throughput Δ: +2.62 tok/s
- TTFT Δ: +233.62 ms (positive = Agent B faster TTFT)
