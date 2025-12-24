# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 57.42s
- Sequential Estimate: 114.63s
- Speedup: 2.00x
- Efficiency: 99.8% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.16 tok/s
- TTFT: 802.77 ms
- Total Duration: 57386.83 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 40.64 tok/s
- TTFT: 810.73 ms
- Total Duration: 57182.67 ms

## Delta (B - A)
- Throughput Δ: -0.53 tok/s
- TTFT Δ: -7.96 ms (positive = Agent B faster TTFT)
