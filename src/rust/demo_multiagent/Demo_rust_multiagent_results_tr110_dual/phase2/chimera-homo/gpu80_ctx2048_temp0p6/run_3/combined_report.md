# Rust Multi-Agent Report - Run 3

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 13.59s
- Sequential Estimate: 25.10s
- Speedup: 1.85x
- Efficiency: 92.3% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://127.0.0.1:11434
- Config: num_gpu=80, num_ctx=2048, temp=0.6, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 41.60 tok/s
- TTFT: 202.50 ms
- Total Duration: 11508.23 ms

## Agent B (Chimera Agent B)
- Base URL: http://127.0.0.1:11435
- Config: num_gpu=80, num_ctx=2048, temp=0.6, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 51.50 tok/s
- TTFT: 347.84 ms
- Total Duration: 13587.12 ms

## Delta (B - A)
- Throughput Δ: +9.91 tok/s
- TTFT Δ: -145.34 ms (positive = Agent B faster TTFT)
