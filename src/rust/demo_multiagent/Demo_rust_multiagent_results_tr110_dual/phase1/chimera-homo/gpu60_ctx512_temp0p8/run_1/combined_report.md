# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 20.14s
- Sequential Estimate: 38.26s
- Speedup: 1.90x
- Efficiency: 95.0% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://127.0.0.1:11434
- Config: num_gpu=60, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 41.00 tok/s
- TTFT: 7734.46 ms
- Total Duration: 18122.56 ms

## Agent B (Chimera Agent B)
- Base URL: http://127.0.0.1:11435
- Config: num_gpu=60, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 52.43 tok/s
- TTFT: 7610.89 ms
- Total Duration: 20134.01 ms

## Delta (B - A)
- Throughput Δ: +11.43 tok/s
- TTFT Δ: +123.57 ms (positive = Agent B faster TTFT)
