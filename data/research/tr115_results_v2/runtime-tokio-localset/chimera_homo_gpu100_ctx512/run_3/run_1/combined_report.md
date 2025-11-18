# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 53.54s
- Sequential Estimate: 107.06s
- Speedup: 2.00x
- Efficiency: 100.0% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=100, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.18 tok/s
- TTFT: 658.85 ms
- Total Duration: 53526.10 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=100, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 40.93 tok/s
- TTFT: 821.12 ms
- Total Duration: 53507.67 ms

## Delta (B - A)
- Throughput Δ: -0.25 tok/s
- TTFT Δ: -162.27 ms (positive = Agent B faster TTFT)
