# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 47.14s
- Sequential Estimate: 47.13s
- Speedup: 1.00x
- Efficiency: 50.0% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=2048, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 108.69 tok/s
- TTFT: 597.46 ms
- Total Duration: 22915.22 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=2048, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 107.99 tok/s
- TTFT: 589.30 ms
- Total Duration: 24150.15 ms

## Delta (B - A)
- Throughput Δ: -0.70 tok/s
- TTFT Δ: +8.16 ms (positive = Agent B faster TTFT)
