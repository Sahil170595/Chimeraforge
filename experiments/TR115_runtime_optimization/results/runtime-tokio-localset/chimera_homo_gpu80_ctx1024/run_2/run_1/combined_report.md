# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 13.33s
- Sequential Estimate: 24.83s
- Speedup: 1.86x
- Efficiency: 93.2% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=1024, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 40.90 tok/s
- TTFT: 698.17 ms
- Total Duration: 11504.27 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=1024, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 50.95 tok/s
- TTFT: 592.71 ms
- Total Duration: 13324.56 ms

## Delta (B - A)
- Throughput Δ: +10.06 tok/s
- TTFT Δ: +105.46 ms (positive = Agent B faster TTFT)
