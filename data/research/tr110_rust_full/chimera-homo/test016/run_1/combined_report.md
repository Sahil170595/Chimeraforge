# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 55.88s
- Sequential Estimate: 111.49s
- Speedup: 2.00x
- Efficiency: 99.8% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=1024, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.46 tok/s
- TTFT: 598.17 ms
- Total Duration: 55571.67 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=1024, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.39 tok/s
- TTFT: 791.64 ms
- Total Duration: 55845.11 ms

## Delta (B - A)
- Throughput Δ: -0.07 tok/s
- TTFT Δ: -193.47 ms (positive = Agent B faster TTFT)
