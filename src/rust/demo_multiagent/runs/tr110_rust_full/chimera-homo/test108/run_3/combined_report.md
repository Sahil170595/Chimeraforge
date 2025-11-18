# Rust Multi-Agent Report - Run 3

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 51.97s
- Sequential Estimate: 101.85s
- Speedup: 1.96x
- Efficiency: 98.0% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=2048, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 40.54 tok/s
- TTFT: 582.01 ms
- Total Duration: 49850.34 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=2048, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 43.86 tok/s
- TTFT: 661.49 ms
- Total Duration: 51940.60 ms

## Delta (B - A)
- Throughput Δ: +3.31 tok/s
- TTFT Δ: -79.49 ms (positive = Agent B faster TTFT)
