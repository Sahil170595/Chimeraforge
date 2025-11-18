# Rust Multi-Agent Report - Run 4

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 57.89s
- Sequential Estimate: 115.71s
- Speedup: 2.00x
- Efficiency: 99.9% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=60, num_ctx=512, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.09 tok/s
- TTFT: 659.78 ms
- Total Duration: 57800.74 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=60, num_ctx=512, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.17 tok/s
- TTFT: 649.45 ms
- Total Duration: 57856.24 ms

## Delta (B - A)
- Throughput Δ: +0.07 tok/s
- TTFT Δ: +10.33 ms (positive = Agent B faster TTFT)
