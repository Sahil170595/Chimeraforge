# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 12.41s
- Sequential Estimate: 23.69s
- Speedup: 1.91x
- Efficiency: 95.5% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=100, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 42.29 tok/s
- TTFT: 681.26 ms
- Total Duration: 11284.39 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=100, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 49.97 tok/s
- TTFT: 553.22 ms
- Total Duration: 12410.27 ms

## Delta (B - A)
- Throughput Δ: +7.68 tok/s
- TTFT Δ: +128.04 ms (positive = Agent B faster TTFT)
