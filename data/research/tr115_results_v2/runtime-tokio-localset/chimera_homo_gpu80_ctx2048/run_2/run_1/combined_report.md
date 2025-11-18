# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 58.71s
- Sequential Estimate: 114.37s
- Speedup: 1.95x
- Efficiency: 97.4% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=2048, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.02 tok/s
- TTFT: 832.76 ms
- Total Duration: 55634.06 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=2048, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 45.03 tok/s
- TTFT: 845.51 ms
- Total Duration: 58673.65 ms

## Delta (B - A)
- Throughput Δ: +4.01 tok/s
- TTFT Δ: -12.76 ms (positive = Agent B faster TTFT)
