# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 11.95s
- Sequential Estimate: 20.85s
- Speedup: 1.74x
- Efficiency: 87.2% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://127.0.0.1:11434
- Config: num_gpu=80, num_ctx=2048, temp=1, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 42.22 tok/s
- TTFT: 225.22 ms
- Total Duration: 8900.86 ms

## Agent B (Chimera Agent B)
- Base URL: http://127.0.0.1:11435
- Config: num_gpu=80, num_ctx=2048, temp=1, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 58.79 tok/s
- TTFT: 385.50 ms
- Total Duration: 11946.56 ms

## Delta (B - A)
- Throughput Δ: +16.58 tok/s
- TTFT Δ: -160.27 ms (positive = Agent B faster TTFT)
