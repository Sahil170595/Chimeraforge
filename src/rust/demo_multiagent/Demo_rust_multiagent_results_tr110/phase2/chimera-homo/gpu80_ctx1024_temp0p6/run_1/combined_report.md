# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 10.31s
- Sequential Estimate: 17.04s
- Speedup: 1.65x
- Efficiency: 82.6% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=1024, temp=0.6, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 102.68 tok/s
- TTFT: 6753.40 ms
- Total Duration: 10310.74 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=1024, temp=0.6, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 100.94 tok/s
- TTFT: 240.67 ms
- Total Duration: 6725.59 ms

## Delta (B - A)
- Throughput Δ: -1.74 tok/s
- TTFT Δ: +6512.73 ms (positive = Agent B faster TTFT)
