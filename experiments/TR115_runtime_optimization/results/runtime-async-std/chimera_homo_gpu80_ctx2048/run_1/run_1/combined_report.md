# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 10.08s
- Sequential Estimate: 10.08s
- Speedup: 1.00x
- Efficiency: 50.0% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=2048, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 123.04 tok/s
- TTFT: 807.78 ms
- Total Duration: 3870.57 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=2048, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 121.25 tok/s
- TTFT: 594.24 ms
- Total Duration: 6205.01 ms

## Delta (B - A)
- Throughput Δ: -1.78 tok/s
- TTFT Δ: +213.54 ms (positive = Agent B faster TTFT)
