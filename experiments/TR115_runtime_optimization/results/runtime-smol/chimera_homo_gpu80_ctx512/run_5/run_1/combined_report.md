# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 12.13s
- Sequential Estimate: 21.93s
- Speedup: 1.81x
- Efficiency: 90.4% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 42.75 tok/s
- TTFT: 663.37 ms
- Total Duration: 9808.39 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 57.97 tok/s
- TTFT: 577.88 ms
- Total Duration: 12125.99 ms

## Delta (B - A)
- Throughput Δ: +15.22 tok/s
- TTFT Δ: +85.49 ms (positive = Agent B faster TTFT)
