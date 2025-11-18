# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 54.37s
- Sequential Estimate: 106.77s
- Speedup: 1.96x
- Efficiency: 98.2% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=1024, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 40.95 tok/s
- TTFT: 777.54 ms
- Total Duration: 52364.63 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=1024, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 43.64 tok/s
- TTFT: 822.57 ms
- Total Duration: 54339.72 ms

## Delta (B - A)
- Throughput Δ: +2.70 tok/s
- TTFT Δ: -45.03 ms (positive = Agent B faster TTFT)
