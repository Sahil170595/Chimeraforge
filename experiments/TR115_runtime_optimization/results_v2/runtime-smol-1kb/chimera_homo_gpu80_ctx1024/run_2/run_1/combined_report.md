# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 56.19s
- Sequential Estimate: 112.26s
- Speedup: 2.00x
- Efficiency: 99.9% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=1024, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 40.87 tok/s
- TTFT: 1003.32 ms
- Total Duration: 56153.31 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=1024, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 40.88 tok/s
- TTFT: 1067.99 ms
- Total Duration: 56039.85 ms

## Delta (B - A)
- Throughput Δ: +0.01 tok/s
- TTFT Δ: -64.67 ms (positive = Agent B faster TTFT)
