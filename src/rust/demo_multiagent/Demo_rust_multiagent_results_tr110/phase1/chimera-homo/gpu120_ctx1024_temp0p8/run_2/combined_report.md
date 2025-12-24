# Rust Multi-Agent Report - Run 2

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 10.45s
- Sequential Estimate: 17.17s
- Speedup: 1.64x
- Efficiency: 82.2% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=120, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 100.03 tok/s
- TTFT: 6755.43 ms
- Total Duration: 10447.06 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11434
- Config: num_gpu=120, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 99.56 tok/s
- TTFT: 222.42 ms
- Total Duration: 6725.78 ms

## Delta (B - A)
- Throughput Δ: -0.47 tok/s
- TTFT Δ: +6533.01 ms (positive = Agent B faster TTFT)
