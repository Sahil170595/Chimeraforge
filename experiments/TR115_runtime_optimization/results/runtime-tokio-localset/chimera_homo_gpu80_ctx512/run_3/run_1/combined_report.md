# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 13.71s
- Sequential Estimate: 24.99s
- Speedup: 1.82x
- Efficiency: 91.2% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 40.66 tok/s
- TTFT: 696.38 ms
- Total Duration: 11283.22 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 53.63 tok/s
- TTFT: 594.99 ms
- Total Duration: 13708.28 ms

## Delta (B - A)
- Throughput Δ: +12.97 tok/s
- TTFT Δ: +101.39 ms (positive = Agent B faster TTFT)
