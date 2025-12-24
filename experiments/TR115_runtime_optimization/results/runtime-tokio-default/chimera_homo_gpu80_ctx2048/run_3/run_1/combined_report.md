# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 12.96s
- Sequential Estimate: 24.50s
- Speedup: 1.89x
- Efficiency: 94.5% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=2048, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.01 tok/s
- TTFT: 802.94 ms
- Total Duration: 11539.91 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=2048, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 49.76 tok/s
- TTFT: 598.94 ms
- Total Duration: 12959.97 ms

## Delta (B - A)
- Throughput Δ: +8.75 tok/s
- TTFT Δ: +204.00 ms (positive = Agent B faster TTFT)
