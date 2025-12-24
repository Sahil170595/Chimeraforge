# Rust Multi-Agent Report - Run 3

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 12.42s
- Sequential Estimate: 22.60s
- Speedup: 1.82x
- Efficiency: 91.0% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://127.0.0.1:11434
- Config: num_gpu=80, num_ctx=1024, temp=1, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 41.81 tok/s
- TTFT: 200.38 ms
- Total Duration: 10176.83 ms

## Agent B (Chimera Agent B)
- Base URL: http://127.0.0.1:11435
- Config: num_gpu=80, num_ctx=1024, temp=1, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 53.60 tok/s
- TTFT: 341.27 ms
- Total Duration: 12419.56 ms

## Delta (B - A)
- Throughput Δ: +11.79 tok/s
- TTFT Δ: -140.89 ms (positive = Agent B faster TTFT)
