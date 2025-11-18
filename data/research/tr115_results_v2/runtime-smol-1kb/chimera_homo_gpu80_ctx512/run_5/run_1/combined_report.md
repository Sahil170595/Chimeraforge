# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 53.80s
- Sequential Estimate: 105.68s
- Speedup: 1.96x
- Efficiency: 98.2% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.20 tok/s
- TTFT: 1001.24 ms
- Total Duration: 51849.61 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 43.60 tok/s
- TTFT: 1065.66 ms
- Total Duration: 53767.40 ms

## Delta (B - A)
- Throughput Δ: +2.40 tok/s
- TTFT Δ: -64.42 ms (positive = Agent B faster TTFT)
