# Rust Multi-Agent Report – Run 3

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 24.62s
- Sequential Estimate: 48.50s
- Speedup: 1.97x
- Efficiency: 98.5% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 27.22 tok/s
- TTFT: 375.91 ms
- Total Duration: 24617.84 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 25.80 tok/s
- TTFT: 226.63 ms
- Total Duration: 23882.18 ms

## Delta (B - A)
- Throughput Δ: -1.42 tok/s
- TTFT Δ: +149.28 ms (positive = Agent B faster TTFT)
