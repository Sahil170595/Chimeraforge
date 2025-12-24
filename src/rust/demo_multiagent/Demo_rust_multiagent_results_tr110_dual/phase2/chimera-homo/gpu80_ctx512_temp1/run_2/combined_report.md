# Rust Multi-Agent Report - Run 2

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 13.72s
- Sequential Estimate: 26.11s
- Speedup: 1.90x
- Efficiency: 95.2% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://127.0.0.1:11434
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 41.13 tok/s
- TTFT: 255.19 ms
- Total Duration: 12395.38 ms

## Agent B (Chimera Agent B)
- Base URL: http://127.0.0.1:11435
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 47.84 tok/s
- TTFT: 316.77 ms
- Total Duration: 13716.40 ms

## Delta (B - A)
- Throughput Δ: +6.70 tok/s
- TTFT Δ: -61.58 ms (positive = Agent B faster TTFT)
