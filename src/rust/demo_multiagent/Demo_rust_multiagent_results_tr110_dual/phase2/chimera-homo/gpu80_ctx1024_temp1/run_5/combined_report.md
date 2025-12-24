# Rust Multi-Agent Report - Run 5

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 13.70s
- Sequential Estimate: 25.71s
- Speedup: 1.88x
- Efficiency: 93.9% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://127.0.0.1:11434
- Config: num_gpu=80, num_ctx=1024, temp=1, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 41.58 tok/s
- TTFT: 211.33 ms
- Total Duration: 12012.38 ms

## Agent B (Chimera Agent B)
- Base URL: http://127.0.0.1:11435
- Config: num_gpu=80, num_ctx=1024, temp=1, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 49.25 tok/s
- TTFT: 350.53 ms
- Total Duration: 13696.33 ms

## Delta (B - A)
- Throughput Δ: +7.67 tok/s
- TTFT Δ: -139.21 ms (positive = Agent B faster TTFT)
