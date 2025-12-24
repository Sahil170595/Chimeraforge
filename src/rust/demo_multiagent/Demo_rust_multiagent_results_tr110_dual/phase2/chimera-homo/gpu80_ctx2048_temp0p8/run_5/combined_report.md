# Rust Multi-Agent Report - Run 5

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 4.71s
- Sequential Estimate: 6.84s
- Speedup: 1.45x
- Efficiency: 72.7% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Chimera Agent A)
- Base URL: http://127.0.0.1:11434
- Config: num_gpu=80, num_ctx=2048, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 83.66 tok/s
- TTFT: 205.59 ms
- Total Duration: 4705.31 ms

## Agent B (Chimera Agent B)
- Base URL: http://127.0.0.1:11435
- Config: num_gpu=80, num_ctx=2048, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 42.13 tok/s
- TTFT: 349.57 ms
- Total Duration: 2134.36 ms

## Delta (B - A)
- Throughput Δ: -41.53 tok/s
- TTFT Δ: -143.98 ms (positive = Agent B faster TTFT)
