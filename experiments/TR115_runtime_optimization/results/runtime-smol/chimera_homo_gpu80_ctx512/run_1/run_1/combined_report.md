# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 10.98s
- Sequential Estimate: 16.43s
- Speedup: 1.50x
- Efficiency: 74.8% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 98.82 tok/s
- TTFT: 648.36 ms
- Total Duration: 5443.53 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 109.31 tok/s
- TTFT: 4507.56 ms
- Total Duration: 10981.92 ms

## Delta (B - A)
- Throughput Δ: +10.50 tok/s
- TTFT Δ: -3859.19 ms (positive = Agent B faster TTFT)
