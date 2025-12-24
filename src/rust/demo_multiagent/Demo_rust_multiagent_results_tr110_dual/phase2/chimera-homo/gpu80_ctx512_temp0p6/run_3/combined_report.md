# Rust Multi-Agent Report - Run 3

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 13.23s
- Sequential Estimate: 24.00s
- Speedup: 1.81x
- Efficiency: 90.7% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://127.0.0.1:11434
- Config: num_gpu=80, num_ctx=512, temp=0.6, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 41.25 tok/s
- TTFT: 249.90 ms
- Total Duration: 10763.22 ms

## Agent B (Chimera Agent B)
- Base URL: http://127.0.0.1:11435
- Config: num_gpu=80, num_ctx=512, temp=0.6, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 53.83 tok/s
- TTFT: 313.07 ms
- Total Duration: 13231.96 ms

## Delta (B - A)
- Throughput Δ: +12.58 tok/s
- TTFT Δ: -63.17 ms (positive = Agent B faster TTFT)
