# Rust Multi-Agent Report - Run 5

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 12.35s
- Sequential Estimate: 21.94s
- Speedup: 1.78x
- Efficiency: 88.8% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://127.0.0.1:11434
- Config: num_gpu=60, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 41.31 tok/s
- TTFT: 299.81 ms
- Total Duration: 9586.49 ms

## Agent B (Chimera Agent B)
- Base URL: http://127.0.0.1:11435
- Config: num_gpu=60, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 56.91 tok/s
- TTFT: 301.33 ms
- Total Duration: 12352.59 ms

## Delta (B - A)
- Throughput Δ: +15.60 tok/s
- TTFT Δ: -1.52 ms (positive = Agent B faster TTFT)
