# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 11.05s
- Sequential Estimate: 15.19s
- Speedup: 1.37x
- Efficiency: 68.7% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=2048, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 100.53 tok/s
- TTFT: 214.78 ms
- Total Duration: 4135.46 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=2048, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 101.31 tok/s
- TTFT: 4166.59 ms
- Total Duration: 11054.04 ms

## Delta (B - A)
- Throughput Δ: +0.78 tok/s
- TTFT Δ: -3951.81 ms (positive = Agent B faster TTFT)
