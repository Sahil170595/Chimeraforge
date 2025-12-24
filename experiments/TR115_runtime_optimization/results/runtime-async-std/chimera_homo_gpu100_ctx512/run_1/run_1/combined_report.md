# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 18.25s
- Sequential Estimate: 18.25s
- Speedup: 1.00x
- Efficiency: 50.0% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=100, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 122.98 tok/s
- TTFT: 4491.74 ms
- Total Duration: 7773.64 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=100, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 121.54 tok/s
- TTFT: 4832.10 ms
- Total Duration: 10478.84 ms

## Delta (B - A)
- Throughput Δ: -1.44 tok/s
- TTFT Δ: -340.36 ms (positive = Agent B faster TTFT)
