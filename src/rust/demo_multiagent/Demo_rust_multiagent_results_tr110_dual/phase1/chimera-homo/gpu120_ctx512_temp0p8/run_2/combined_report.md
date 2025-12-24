# Rust Multi-Agent Report - Run 2

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 12.01s
- Sequential Estimate: 21.36s
- Speedup: 1.78x
- Efficiency: 88.9% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://127.0.0.1:11434
- Config: num_gpu=120, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 41.29 tok/s
- TTFT: 252.84 ms
- Total Duration: 9347.71 ms

## Agent B (Chimera Agent B)
- Base URL: http://127.0.0.1:11435
- Config: num_gpu=120, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 56.70 tok/s
- TTFT: 310.84 ms
- Total Duration: 12013.27 ms

## Delta (B - A)
- Throughput Δ: +15.41 tok/s
- TTFT Δ: -58.00 ms (positive = Agent B faster TTFT)
