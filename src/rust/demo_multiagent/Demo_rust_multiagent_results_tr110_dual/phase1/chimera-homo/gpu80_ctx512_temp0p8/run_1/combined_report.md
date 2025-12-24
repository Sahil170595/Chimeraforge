# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 19.98s
- Sequential Estimate: 37.96s
- Speedup: 1.90x
- Efficiency: 95.0% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://127.0.0.1:11434
- Config: num_gpu=80, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 41.16 tok/s
- TTFT: 7854.87 ms
- Total Duration: 17988.06 ms

## Agent B (Chimera Agent B)
- Base URL: http://127.0.0.1:11435
- Config: num_gpu=80, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 52.23 tok/s
- TTFT: 7794.59 ms
- Total Duration: 19975.27 ms

## Delta (B - A)
- Throughput Δ: +11.07 tok/s
- TTFT Δ: +60.28 ms (positive = Agent B faster TTFT)
