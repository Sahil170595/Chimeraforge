# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 4.91s
- Sequential Estimate: 6.71s
- Speedup: 1.37x
- Efficiency: 68.4% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=1024, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 98.90 tok/s
- TTFT: 947.65 ms
- Total Duration: 4906.65 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=1024, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 49.32 tok/s
- TTFT: 674.93 ms
- Total Duration: 1801.87 ms

## Delta (B - A)
- Throughput Δ: -49.58 tok/s
- TTFT Δ: +272.72 ms (positive = Agent B faster TTFT)
