# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 12.88s
- Sequential Estimate: 23.51s
- Speedup: 1.83x
- Efficiency: 91.3% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=1024, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.18 tok/s
- TTFT: 697.83 ms
- Total Duration: 10628.22 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=1024, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 54.01 tok/s
- TTFT: 594.21 ms
- Total Duration: 12876.84 ms

## Delta (B - A)
- Throughput Δ: +12.82 tok/s
- TTFT Δ: +103.62 ms (positive = Agent B faster TTFT)
