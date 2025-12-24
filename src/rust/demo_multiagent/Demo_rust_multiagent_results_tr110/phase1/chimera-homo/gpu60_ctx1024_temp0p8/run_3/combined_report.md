# Rust Multi-Agent Report - Run 3

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 10.95s
- Sequential Estimate: 15.20s
- Speedup: 1.39x
- Efficiency: 69.4% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=60, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 100.47 tok/s
- TTFT: 213.92 ms
- Total Duration: 4247.34 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11434
- Config: num_gpu=60, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 100.14 tok/s
- TTFT: 4275.94 ms
- Total Duration: 10950.86 ms

## Delta (B - A)
- Throughput Δ: -0.33 tok/s
- TTFT Δ: -4062.03 ms (positive = Agent B faster TTFT)
