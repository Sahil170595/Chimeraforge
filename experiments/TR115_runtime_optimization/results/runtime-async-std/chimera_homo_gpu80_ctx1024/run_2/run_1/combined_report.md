# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 10.46s
- Sequential Estimate: 10.46s
- Speedup: 1.00x
- Efficiency: 50.0% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=1024, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 123.58 tok/s
- TTFT: 894.66 ms
- Total Duration: 4240.47 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=1024, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 121.37 tok/s
- TTFT: 609.94 ms
- Total Duration: 6214.78 ms

## Delta (B - A)
- Throughput Δ: -2.21 tok/s
- TTFT Δ: +284.72 ms (positive = Agent B faster TTFT)
