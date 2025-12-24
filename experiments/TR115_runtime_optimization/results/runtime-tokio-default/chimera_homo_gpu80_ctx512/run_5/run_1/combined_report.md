# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 14.08s
- Sequential Estimate: 26.61s
- Speedup: 1.89x
- Efficiency: 94.5% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 40.92 tok/s
- TTFT: 763.82 ms
- Total Duration: 12528.26 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 49.56 tok/s
- TTFT: 607.63 ms
- Total Duration: 14076.99 ms

## Delta (B - A)
- Throughput Δ: +8.64 tok/s
- TTFT Δ: +156.19 ms (positive = Agent B faster TTFT)
