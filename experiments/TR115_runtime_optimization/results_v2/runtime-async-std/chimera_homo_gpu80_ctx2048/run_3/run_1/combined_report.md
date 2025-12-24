# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 45.02s
- Sequential Estimate: 45.02s
- Speedup: 1.00x
- Efficiency: 50.0% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=2048, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 107.83 tok/s
- TTFT: 592.86 ms
- Total Duration: 21710.73 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=2048, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 108.17 tok/s
- TTFT: 584.74 ms
- Total Duration: 23240.91 ms

## Delta (B - A)
- Throughput Δ: +0.34 tok/s
- TTFT Δ: +8.12 ms (positive = Agent B faster TTFT)
