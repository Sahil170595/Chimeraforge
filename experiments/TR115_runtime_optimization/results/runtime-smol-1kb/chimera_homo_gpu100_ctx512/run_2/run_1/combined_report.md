# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 11.86s
- Sequential Estimate: 21.13s
- Speedup: 1.78x
- Efficiency: 89.0% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=100, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 42.62 tok/s
- TTFT: 865.00 ms
- Total Duration: 9261.50 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=100, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 60.11 tok/s
- TTFT: 728.58 ms
- Total Duration: 11864.50 ms

## Delta (B - A)
- Throughput Δ: +17.49 tok/s
- TTFT Δ: +136.42 ms (positive = Agent B faster TTFT)
