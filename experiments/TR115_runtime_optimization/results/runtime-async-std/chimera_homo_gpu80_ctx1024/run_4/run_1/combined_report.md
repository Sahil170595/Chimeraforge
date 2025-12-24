# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 10.43s
- Sequential Estimate: 10.43s
- Speedup: 1.00x
- Efficiency: 50.0% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=1024, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 122.36 tok/s
- TTFT: 887.24 ms
- Total Duration: 4173.53 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=1024, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 121.86 tok/s
- TTFT: 610.47 ms
- Total Duration: 6254.70 ms

## Delta (B - A)
- Throughput Δ: -0.51 tok/s
- TTFT Δ: +276.77 ms (positive = Agent B faster TTFT)
