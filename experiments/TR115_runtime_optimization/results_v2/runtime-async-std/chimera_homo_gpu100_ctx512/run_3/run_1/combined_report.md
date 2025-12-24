# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 118.06s
- Sequential Estimate: 118.06s
- Speedup: 1.00x
- Efficiency: 50.0% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=100, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 39.41 tok/s
- TTFT: 858.98 ms
- Total Duration: 59287.33 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=100, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 40.57 tok/s
- TTFT: 1279.09 ms
- Total Duration: 58710.07 ms

## Delta (B - A)
- Throughput Δ: +1.17 tok/s
- TTFT Δ: -420.11 ms (positive = Agent B faster TTFT)
