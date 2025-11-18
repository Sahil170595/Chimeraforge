# Rust Multi-Agent Report - Run 3

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 53.18s
- Sequential Estimate: 104.17s
- Speedup: 1.96x
- Efficiency: 97.9% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=120, num_ctx=512, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 43.66 tok/s
- TTFT: 675.09 ms
- Total Duration: 53135.63 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=120, num_ctx=512, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 40.74 tok/s
- TTFT: 675.49 ms
- Total Duration: 50956.29 ms

## Delta (B - A)
- Throughput Δ: -2.93 tok/s
- TTFT Δ: -0.41 ms (positive = Agent B faster TTFT)
