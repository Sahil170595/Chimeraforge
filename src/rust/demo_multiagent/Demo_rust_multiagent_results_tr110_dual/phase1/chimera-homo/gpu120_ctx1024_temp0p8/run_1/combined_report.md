# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 13.20s
- Sequential Estimate: 23.98s
- Speedup: 1.82x
- Efficiency: 90.8% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://127.0.0.1:11434
- Config: num_gpu=120, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 41.09 tok/s
- TTFT: 317.05 ms
- Total Duration: 10777.39 ms

## Agent B (Chimera Agent B)
- Base URL: http://127.0.0.1:11435
- Config: num_gpu=120, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 53.82 tok/s
- TTFT: 312.51 ms
- Total Duration: 13200.34 ms

## Delta (B - A)
- Throughput Δ: +12.73 tok/s
- TTFT Δ: +4.54 ms (positive = Agent B faster TTFT)
