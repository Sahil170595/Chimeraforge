# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 54.83s
- Sequential Estimate: 107.37s
- Speedup: 1.96x
- Efficiency: 97.9% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=1024, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 44.31 tok/s
- TTFT: 731.33 ms
- Total Duration: 54802.20 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=1024, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 40.98 tok/s
- TTFT: 814.79 ms
- Total Duration: 52510.23 ms

## Delta (B - A)
- Throughput Δ: -3.33 tok/s
- TTFT Δ: -83.46 ms (positive = Agent B faster TTFT)
