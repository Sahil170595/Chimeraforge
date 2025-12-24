# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 10.29s
- Sequential Estimate: 16.93s
- Speedup: 1.65x
- Efficiency: 82.3% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 100.95 tok/s
- TTFT: 6669.19 ms
- Total Duration: 10287.59 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 100.05 tok/s
- TTFT: 219.76 ms
- Total Duration: 6640.63 ms

## Delta (B - A)
- Throughput Δ: -0.90 tok/s
- TTFT Δ: +6449.43 ms (positive = Agent B faster TTFT)
