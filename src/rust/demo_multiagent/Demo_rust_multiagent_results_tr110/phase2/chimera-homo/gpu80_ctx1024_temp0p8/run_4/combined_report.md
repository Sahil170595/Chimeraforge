# Rust Multi-Agent Report - Run 4

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 10.84s
- Sequential Estimate: 15.30s
- Speedup: 1.41x
- Efficiency: 70.5% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 100.59 tok/s
- TTFT: 215.81 ms
- Total Duration: 4453.71 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 100.37 tok/s
- TTFT: 4482.37 ms
- Total Duration: 10844.37 ms

## Delta (B - A)
- Throughput Δ: -0.22 tok/s
- TTFT Δ: -4266.57 ms (positive = Agent B faster TTFT)
