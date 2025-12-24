# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 10.24s
- Sequential Estimate: 10.24s
- Speedup: 1.00x
- Efficiency: 50.0% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=2048, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 122.54 tok/s
- TTFT: 785.17 ms
- Total Duration: 4136.55 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=2048, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 121.55 tok/s
- TTFT: 590.29 ms
- Total Duration: 6101.66 ms

## Delta (B - A)
- Throughput Δ: -0.99 tok/s
- TTFT Δ: +194.88 ms (positive = Agent B faster TTFT)
