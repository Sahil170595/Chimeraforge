# Rust Multi-Agent Report - Run 2

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 10.06s
- Sequential Estimate: 13.96s
- Speedup: 1.39x
- Efficiency: 69.4% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 100.63 tok/s
- TTFT: 220.67 ms
- Total Duration: 3901.42 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 100.53 tok/s
- TTFT: 3929.51 ms
- Total Duration: 10061.18 ms

## Delta (B - A)
- Throughput Δ: -0.10 tok/s
- TTFT Δ: -3708.83 ms (positive = Agent B faster TTFT)
