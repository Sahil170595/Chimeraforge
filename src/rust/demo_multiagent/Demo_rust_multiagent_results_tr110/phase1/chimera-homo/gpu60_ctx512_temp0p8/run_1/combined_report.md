# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 14.98s
- Sequential Estimate: 25.73s
- Speedup: 1.72x
- Efficiency: 85.9% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=60, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 100.88 tok/s
- TTFT: 10777.36 ms
- Total Duration: 14980.35 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11434
- Config: num_gpu=60, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 99.16 tok/s
- TTFT: 3521.11 ms
- Total Duration: 10749.23 ms

## Delta (B - A)
- Throughput Δ: -1.72 tok/s
- TTFT Δ: +7256.25 ms (positive = Agent B faster TTFT)
