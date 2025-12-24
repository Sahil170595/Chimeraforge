# Rust Multi-Agent Report - Run 5

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 12.62s
- Sequential Estimate: 22.16s
- Speedup: 1.76x
- Efficiency: 87.8% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://127.0.0.1:11434
- Config: num_gpu=80, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 41.22 tok/s
- TTFT: 289.62 ms
- Total Duration: 9538.57 ms

## Agent B (Chimera Agent B)
- Base URL: http://127.0.0.1:11435
- Config: num_gpu=80, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 58.44 tok/s
- TTFT: 311.23 ms
- Total Duration: 12617.38 ms

## Delta (B - A)
- Throughput Δ: +17.22 tok/s
- TTFT Δ: -21.61 ms (positive = Agent B faster TTFT)
