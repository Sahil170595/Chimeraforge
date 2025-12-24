# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 10.20s
- Sequential Estimate: 16.76s
- Speedup: 1.64x
- Efficiency: 82.2% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=1024, temp=0.6, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 103.10 tok/s
- TTFT: 6594.42 ms
- Total Duration: 10196.00 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=1024, temp=0.6, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 101.90 tok/s
- TTFT: 191.39 ms
- Total Duration: 6567.62 ms

## Delta (B - A)
- Throughput Δ: -1.20 tok/s
- TTFT Δ: +6403.03 ms (positive = Agent B faster TTFT)
