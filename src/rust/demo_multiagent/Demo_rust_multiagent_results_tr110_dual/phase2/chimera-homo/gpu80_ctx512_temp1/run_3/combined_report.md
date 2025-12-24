# Rust Multi-Agent Report - Run 3

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 4.92s
- Sequential Estimate: 7.15s
- Speedup: 1.45x
- Efficiency: 72.6% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Chimera Agent A)
- Base URL: http://127.0.0.1:11434
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 83.41 tok/s
- TTFT: 260.69 ms
- Total Duration: 4921.54 ms

## Agent B (Chimera Agent B)
- Base URL: http://127.0.0.1:11435
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 41.80 tok/s
- TTFT: 330.19 ms
- Total Duration: 2226.73 ms

## Delta (B - A)
- Throughput Δ: -41.60 tok/s
- TTFT Δ: -69.50 ms (positive = Agent B faster TTFT)
