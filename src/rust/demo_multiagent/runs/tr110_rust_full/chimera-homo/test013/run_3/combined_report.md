# Rust Multi-Agent Report - Run 3

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 56.12s
- Sequential Estimate: 109.28s
- Speedup: 1.95x
- Efficiency: 97.4% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=60, num_ctx=512, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.02 tok/s
- TTFT: 657.60 ms
- Total Duration: 53127.60 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=60, num_ctx=512, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 44.96 tok/s
- TTFT: 649.76 ms
- Total Duration: 56093.43 ms

## Delta (B - A)
- Throughput Δ: +3.94 tok/s
- TTFT Δ: +7.84 ms (positive = Agent B faster TTFT)
