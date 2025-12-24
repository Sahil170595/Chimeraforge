# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 56.53s
- Sequential Estimate: 112.92s
- Speedup: 2.00x
- Efficiency: 99.9% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=100, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.26 tok/s
- TTFT: 1022.47 ms
- Total Duration: 56485.83 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=100, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.00 tok/s
- TTFT: 1063.75 ms
- Total Duration: 56345.22 ms

## Delta (B - A)
- Throughput Δ: -0.26 tok/s
- TTFT Δ: -41.28 ms (positive = Agent B faster TTFT)
