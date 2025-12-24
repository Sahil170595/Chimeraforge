# Rust Multi-Agent Report - Run 4

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 13.80s
- Sequential Estimate: 25.37s
- Speedup: 1.84x
- Efficiency: 91.9% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://127.0.0.1:11434
- Config: num_gpu=80, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 41.14 tok/s
- TTFT: 321.17 ms
- Total Duration: 11570.65 ms

## Agent B (Chimera Agent B)
- Base URL: http://127.0.0.1:11435
- Config: num_gpu=80, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 52.19 tok/s
- TTFT: 291.94 ms
- Total Duration: 13797.90 ms

## Delta (B - A)
- Throughput Δ: +11.04 tok/s
- TTFT Δ: +29.23 ms (positive = Agent B faster TTFT)
