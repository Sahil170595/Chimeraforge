# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 14.44s
- Sequential Estimate: 14.44s
- Speedup: 1.00x
- Efficiency: 50.0% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 122.84 tok/s
- TTFT: 840.95 ms
- Total Duration: 4449.63 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 121.24 tok/s
- TTFT: 3618.04 ms
- Total Duration: 9992.56 ms

## Delta (B - A)
- Throughput Δ: -1.60 tok/s
- TTFT Δ: -2777.09 ms (positive = Agent B faster TTFT)
