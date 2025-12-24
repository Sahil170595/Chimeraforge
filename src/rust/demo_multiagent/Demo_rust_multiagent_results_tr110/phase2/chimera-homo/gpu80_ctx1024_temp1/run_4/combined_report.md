# Rust Multi-Agent Report - Run 4

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 10.72s
- Sequential Estimate: 15.28s
- Speedup: 1.43x
- Efficiency: 71.3% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=1024, temp=1, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 101.76 tok/s
- TTFT: 213.97 ms
- Total Duration: 4559.68 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=1024, temp=1, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 100.49 tok/s
- TTFT: 4588.07 ms
- Total Duration: 10722.63 ms

## Delta (B - A)
- Throughput Δ: -1.27 tok/s
- TTFT Δ: -4374.11 ms (positive = Agent B faster TTFT)
