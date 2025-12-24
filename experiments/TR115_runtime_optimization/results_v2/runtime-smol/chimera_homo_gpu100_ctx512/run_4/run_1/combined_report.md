# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 54.16s
- Sequential Estimate: 105.63s
- Speedup: 1.95x
- Efficiency: 97.5% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=100, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 42.60 tok/s
- TTFT: 781.20 ms
- Total Duration: 51439.96 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=100, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 46.11 tok/s
- TTFT: 825.17 ms
- Total Duration: 54115.76 ms

## Delta (B - A)
- Throughput Δ: +3.51 tok/s
- TTFT Δ: -43.97 ms (positive = Agent B faster TTFT)
