# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 4.90s
- Sequential Estimate: 7.08s
- Speedup: 1.45x
- Efficiency: 72.3% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=2048, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 93.53 tok/s
- TTFT: 677.38 ms
- Total Duration: 4895.59 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=2048, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 47.78 tok/s
- TTFT: 572.84 ms
- Total Duration: 2185.22 ms

## Delta (B - A)
- Throughput Δ: -45.75 tok/s
- TTFT Δ: +104.54 ms (positive = Agent B faster TTFT)
