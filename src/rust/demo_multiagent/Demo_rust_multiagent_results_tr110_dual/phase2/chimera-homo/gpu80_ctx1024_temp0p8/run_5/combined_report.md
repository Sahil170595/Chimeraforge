# Rust Multi-Agent Report - Run 5

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 12.94s
- Sequential Estimate: 22.08s
- Speedup: 1.71x
- Efficiency: 85.3% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://127.0.0.1:11434
- Config: num_gpu=80, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 42.10 tok/s
- TTFT: 202.85 ms
- Total Duration: 9136.44 ms

## Agent B (Chimera Agent B)
- Base URL: http://127.0.0.1:11435
- Config: num_gpu=80, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 61.42 tok/s
- TTFT: 363.91 ms
- Total Duration: 12939.88 ms

## Delta (B - A)
- Throughput Δ: +19.32 tok/s
- TTFT Δ: -161.06 ms (positive = Agent B faster TTFT)
