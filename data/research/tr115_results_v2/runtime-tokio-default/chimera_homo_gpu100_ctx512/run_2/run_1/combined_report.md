# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 55.54s
- Sequential Estimate: 110.09s
- Speedup: 1.98x
- Efficiency: 99.1% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=100, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 42.53 tok/s
- TTFT: 832.17 ms
- Total Duration: 55470.98 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=100, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.24 tok/s
- TTFT: 831.17 ms
- Total Duration: 54483.74 ms

## Delta (B - A)
- Throughput Δ: -1.29 tok/s
- TTFT Δ: +1.00 ms (positive = Agent B faster TTFT)
