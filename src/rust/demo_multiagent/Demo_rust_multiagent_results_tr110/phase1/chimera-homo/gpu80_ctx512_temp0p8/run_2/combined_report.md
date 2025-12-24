# Rust Multi-Agent Report - Run 2

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 10.30s
- Sequential Estimate: 14.22s
- Speedup: 1.38x
- Efficiency: 69.0% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 100.72 tok/s
- TTFT: 213.31 ms
- Total Duration: 3919.78 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 100.26 tok/s
- TTFT: 3949.21 ms
- Total Duration: 10297.30 ms

## Delta (B - A)
- Throughput Δ: -0.45 tok/s
- TTFT Δ: -3735.90 ms (positive = Agent B faster TTFT)
