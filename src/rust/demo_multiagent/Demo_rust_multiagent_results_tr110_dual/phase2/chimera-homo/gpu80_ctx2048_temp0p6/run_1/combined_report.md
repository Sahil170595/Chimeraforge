# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 13.39s
- Sequential Estimate: 24.73s
- Speedup: 1.85x
- Efficiency: 92.3% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://127.0.0.1:11434
- Config: num_gpu=80, num_ctx=2048, temp=0.6, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 41.67 tok/s
- TTFT: 213.40 ms
- Total Duration: 11339.57 ms

## Agent B (Chimera Agent B)
- Base URL: http://127.0.0.1:11435
- Config: num_gpu=80, num_ctx=2048, temp=0.6, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 51.52 tok/s
- TTFT: 359.35 ms
- Total Duration: 13390.56 ms

## Delta (B - A)
- Throughput Δ: +9.85 tok/s
- TTFT Δ: -145.95 ms (positive = Agent B faster TTFT)
