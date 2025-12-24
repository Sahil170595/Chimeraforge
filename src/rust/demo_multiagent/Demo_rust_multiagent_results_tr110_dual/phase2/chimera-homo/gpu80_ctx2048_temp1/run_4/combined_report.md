# Rust Multi-Agent Report - Run 4

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 12.67s
- Sequential Estimate: 22.40s
- Speedup: 1.77x
- Efficiency: 88.4% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://127.0.0.1:11434
- Config: num_gpu=80, num_ctx=2048, temp=1, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 40.98 tok/s
- TTFT: 297.80 ms
- Total Duration: 9728.64 ms

## Agent B (Chimera Agent B)
- Base URL: http://127.0.0.1:11435
- Config: num_gpu=80, num_ctx=2048, temp=1, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 57.15 tok/s
- TTFT: 302.17 ms
- Total Duration: 12672.69 ms

## Delta (B - A)
- Throughput Δ: +16.17 tok/s
- TTFT Δ: -4.37 ms (positive = Agent B faster TTFT)
