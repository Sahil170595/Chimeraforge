# Rust Multi-Agent Report - Run 4

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 56.27s
- Sequential Estimate: 110.75s
- Speedup: 1.97x
- Efficiency: 98.4% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 42.98 tok/s
- TTFT: 627.73 ms
- Total Duration: 56226.97 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=512, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 40.89 tok/s
- TTFT: 679.18 ms
- Total Duration: 54443.98 ms

## Delta (B - A)
- Throughput Δ: -2.09 tok/s
- TTFT Δ: -51.45 ms (positive = Agent B faster TTFT)
