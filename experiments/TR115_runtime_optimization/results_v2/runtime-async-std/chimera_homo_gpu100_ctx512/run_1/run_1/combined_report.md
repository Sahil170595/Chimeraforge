# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 115.43s
- Sequential Estimate: 115.43s
- Speedup: 1.00x
- Efficiency: 50.0% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=100, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 80.57 tok/s
- TTFT: 13002.11 ms
- Total Duration: 59665.53 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=100, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 74.55 tok/s
- TTFT: 8178.49 ms
- Total Duration: 55701.57 ms

## Delta (B - A)
- Throughput Δ: -6.02 tok/s
- TTFT Δ: +4823.62 ms (positive = Agent B faster TTFT)
