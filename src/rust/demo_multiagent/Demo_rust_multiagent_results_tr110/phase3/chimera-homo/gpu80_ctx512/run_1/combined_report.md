# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 13.17s
- Sequential Estimate: 22.93s
- Speedup: 1.74x
- Efficiency: 87.1% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 102.33 tok/s
- TTFT: 9793.67 ms
- Total Duration: 13166.40 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 100.68 tok/s
- TTFT: 3452.78 ms
- Total Duration: 9767.37 ms

## Delta (B - A)
- Throughput Δ: -1.65 tok/s
- TTFT Δ: +6340.89 ms (positive = Agent B faster TTFT)
