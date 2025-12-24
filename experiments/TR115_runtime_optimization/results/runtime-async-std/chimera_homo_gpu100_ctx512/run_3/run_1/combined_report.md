# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 9.95s
- Sequential Estimate: 9.95s
- Speedup: 1.00x
- Efficiency: 50.0% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=100, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 123.09 tok/s
- TTFT: 851.23 ms
- Total Duration: 3977.77 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=100, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 121.62 tok/s
- TTFT: 619.25 ms
- Total Duration: 5974.66 ms

## Delta (B - A)
- Throughput Δ: -1.47 tok/s
- TTFT Δ: +231.97 ms (positive = Agent B faster TTFT)
