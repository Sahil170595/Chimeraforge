# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 11.07s
- Sequential Estimate: 11.07s
- Speedup: 1.00x
- Efficiency: 50.0% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=1024, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 121.81 tok/s
- TTFT: 894.17 ms
- Total Duration: 5065.96 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=1024, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 121.97 tok/s
- TTFT: 606.84 ms
- Total Duration: 6006.76 ms

## Delta (B - A)
- Throughput Δ: +0.16 tok/s
- TTFT Δ: +287.33 ms (positive = Agent B faster TTFT)
