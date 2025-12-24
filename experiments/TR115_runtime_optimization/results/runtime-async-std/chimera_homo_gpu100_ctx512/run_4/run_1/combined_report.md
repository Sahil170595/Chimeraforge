# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 11.17s
- Sequential Estimate: 11.17s
- Speedup: 1.00x
- Efficiency: 50.0% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=100, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 122.47 tok/s
- TTFT: 784.34 ms
- Total Duration: 4577.70 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=100, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 121.69 tok/s
- TTFT: 594.64 ms
- Total Duration: 6588.13 ms

## Delta (B - A)
- Throughput Δ: -0.78 tok/s
- TTFT Δ: +189.70 ms (positive = Agent B faster TTFT)
