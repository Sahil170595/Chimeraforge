# Rust Multi-Agent Report - Run 3

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 5.08s
- Sequential Estimate: 9.57s
- Speedup: 1.89x
- Efficiency: 94.3% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=1024, temp=0.6, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 100.02 tok/s
- TTFT: 222.55 ms
- Total Duration: 4493.34 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=1024, temp=0.6, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 102.45 tok/s
- TTFT: 4520.45 ms
- Total Duration: 5076.66 ms

## Delta (B - A)
- Throughput Δ: +2.43 tok/s
- TTFT Δ: -4297.91 ms (positive = Agent B faster TTFT)
