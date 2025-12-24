# Rust Multi-Agent Report - Run 4

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 11.16s
- Sequential Estimate: 19.82s
- Speedup: 1.78x
- Efficiency: 88.8% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://127.0.0.1:11434
- Config: num_gpu=80, num_ctx=1024, temp=1, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 42.03 tok/s
- TTFT: 217.30 ms
- Total Duration: 8655.31 ms

## Agent B (Chimera Agent B)
- Base URL: http://127.0.0.1:11435
- Config: num_gpu=80, num_ctx=1024, temp=1, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 56.72 tok/s
- TTFT: 362.18 ms
- Total Duration: 11163.58 ms

## Delta (B - A)
- Throughput Δ: +14.69 tok/s
- TTFT Δ: -144.89 ms (positive = Agent B faster TTFT)
