# Rust Multi-Agent Report - Run 5

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 10.29s
- Sequential Estimate: 14.00s
- Speedup: 1.36x
- Efficiency: 68.0% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 100.83 tok/s
- TTFT: 217.03 ms
- Total Duration: 3709.03 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 101.52 tok/s
- TTFT: 3740.33 ms
- Total Duration: 10287.96 ms

## Delta (B - A)
- Throughput Δ: +0.69 tok/s
- TTFT Δ: -3523.30 ms (positive = Agent B faster TTFT)
