# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 54.99s
- Sequential Estimate: 107.15s
- Speedup: 1.95x
- Efficiency: 97.4% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.09 tok/s
- TTFT: 652.16 ms
- Total Duration: 52144.74 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 44.62 tok/s
- TTFT: 807.16 ms
- Total Duration: 54978.20 ms

## Delta (B - A)
- Throughput Δ: +3.53 tok/s
- TTFT Δ: -155.00 ms (positive = Agent B faster TTFT)
