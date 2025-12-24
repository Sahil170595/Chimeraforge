# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 10.35s
- Sequential Estimate: 14.32s
- Speedup: 1.38x
- Efficiency: 69.2% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 103.42 tok/s
- TTFT: 216.32 ms
- Total Duration: 3970.44 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 102.57 tok/s
- TTFT: 3998.46 ms
- Total Duration: 10349.44 ms

## Delta (B - A)
- Throughput Δ: -0.85 tok/s
- TTFT Δ: -3782.14 ms (positive = Agent B faster TTFT)
