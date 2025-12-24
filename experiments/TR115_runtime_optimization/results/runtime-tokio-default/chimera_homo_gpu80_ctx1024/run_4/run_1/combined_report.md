# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 13.17s
- Sequential Estimate: 24.47s
- Speedup: 1.86x
- Efficiency: 92.9% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=1024, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 40.79 tok/s
- TTFT: 772.97 ms
- Total Duration: 11299.14 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=1024, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 51.67 tok/s
- TTFT: 595.84 ms
- Total Duration: 13173.65 ms

## Delta (B - A)
- Throughput Δ: +10.88 tok/s
- TTFT Δ: +177.12 ms (positive = Agent B faster TTFT)
