# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 53.48s
- Sequential Estimate: 105.75s
- Speedup: 1.98x
- Efficiency: 98.9% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=100, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.03 tok/s
- TTFT: 1055.99 ms
- Total Duration: 52230.22 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=100, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 42.68 tok/s
- TTFT: 1056.94 ms
- Total Duration: 53442.13 ms

## Delta (B - A)
- Throughput Δ: +1.65 tok/s
- TTFT Δ: -0.95 ms (positive = Agent B faster TTFT)
