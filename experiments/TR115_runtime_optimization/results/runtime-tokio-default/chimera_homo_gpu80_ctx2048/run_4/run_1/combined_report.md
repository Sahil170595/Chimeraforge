# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 13.00s
- Sequential Estimate: 24.05s
- Speedup: 1.85x
- Efficiency: 92.5% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=2048, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.04 tok/s
- TTFT: 704.74 ms
- Total Duration: 11044.53 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=2048, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 52.27 tok/s
- TTFT: 593.06 ms
- Total Duration: 13001.80 ms

## Delta (B - A)
- Throughput Δ: +11.23 tok/s
- TTFT Δ: +111.67 ms (positive = Agent B faster TTFT)
