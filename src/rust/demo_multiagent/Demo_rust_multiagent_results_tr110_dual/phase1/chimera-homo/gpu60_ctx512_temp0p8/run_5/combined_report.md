# Rust Multi-Agent Report - Run 5

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 12.01s
- Sequential Estimate: 21.02s
- Speedup: 1.75x
- Efficiency: 87.5% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://127.0.0.1:11434
- Config: num_gpu=60, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 41.69 tok/s
- TTFT: 273.89 ms
- Total Duration: 9009.32 ms

## Agent B (Chimera Agent B)
- Base URL: http://127.0.0.1:11435
- Config: num_gpu=60, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 58.87 tok/s
- TTFT: 321.56 ms
- Total Duration: 12006.17 ms

## Delta (B - A)
- Throughput Δ: +17.18 tok/s
- TTFT Δ: -47.67 ms (positive = Agent B faster TTFT)
