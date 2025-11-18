# Rust Multi-Agent Report - Run 3

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 57.56s
- Sequential Estimate: 112.67s
- Speedup: 1.96x
- Efficiency: 97.9% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=1024, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 44.23 tok/s
- TTFT: 674.47 ms
- Total Duration: 57526.68 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=1024, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.13 tok/s
- TTFT: 665.48 ms
- Total Duration: 55089.58 ms

## Delta (B - A)
- Throughput Δ: -3.10 tok/s
- TTFT Δ: +9.00 ms (positive = Agent B faster TTFT)
