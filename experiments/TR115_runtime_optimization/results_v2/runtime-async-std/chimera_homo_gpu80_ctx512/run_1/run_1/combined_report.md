# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 49.52s
- Sequential Estimate: 49.51s
- Speedup: 1.00x
- Efficiency: 50.0% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 108.29 tok/s
- TTFT: 590.47 ms
- Total Duration: 22211.99 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 107.79 tok/s
- TTFT: 2540.01 ms
- Total Duration: 27234.67 ms

## Delta (B - A)
- Throughput Δ: -0.50 tok/s
- TTFT Δ: -1949.54 ms (positive = Agent B faster TTFT)
