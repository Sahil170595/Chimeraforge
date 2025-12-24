# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 10.33s
- Sequential Estimate: 13.99s
- Speedup: 1.35x
- Efficiency: 67.7% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 103.46 tok/s
- TTFT: 217.36 ms
- Total Duration: 3659.15 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 103.00 tok/s
- TTFT: 3689.59 ms
- Total Duration: 10326.30 ms

## Delta (B - A)
- Throughput Δ: -0.46 tok/s
- TTFT Δ: -3472.23 ms (positive = Agent B faster TTFT)
