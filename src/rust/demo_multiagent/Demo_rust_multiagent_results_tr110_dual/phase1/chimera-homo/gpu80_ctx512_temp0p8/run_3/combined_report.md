# Rust Multi-Agent Report - Run 3

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 13.64s
- Sequential Estimate: 25.00s
- Speedup: 1.83x
- Efficiency: 91.6% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://127.0.0.1:11434
- Config: num_gpu=80, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 41.48 tok/s
- TTFT: 254.86 ms
- Total Duration: 11356.23 ms

## Agent B (Chimera Agent B)
- Base URL: http://127.0.0.1:11435
- Config: num_gpu=80, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 52.82 tok/s
- TTFT: 314.11 ms
- Total Duration: 13642.50 ms

## Delta (B - A)
- Throughput Δ: +11.34 tok/s
- TTFT Δ: -59.24 ms (positive = Agent B faster TTFT)
