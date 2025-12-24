# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 13.46s
- Sequential Estimate: 23.73s
- Speedup: 1.76x
- Efficiency: 88.2% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 40.74 tok/s
- TTFT: 686.49 ms
- Total Duration: 10270.52 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 58.02 tok/s
- TTFT: 598.66 ms
- Total Duration: 13455.16 ms

## Delta (B - A)
- Throughput Δ: +17.28 tok/s
- TTFT Δ: +87.83 ms (positive = Agent B faster TTFT)
