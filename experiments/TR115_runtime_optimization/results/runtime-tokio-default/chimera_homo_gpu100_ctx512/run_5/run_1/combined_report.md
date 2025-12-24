# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 12.74s
- Sequential Estimate: 21.98s
- Speedup: 1.73x
- Efficiency: 86.3% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=100, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 40.85 tok/s
- TTFT: 709.76 ms
- Total Duration: 9243.23 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=100, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 60.85 tok/s
- TTFT: 616.58 ms
- Total Duration: 12738.02 ms

## Delta (B - A)
- Throughput Δ: +20.00 tok/s
- TTFT Δ: +93.18 ms (positive = Agent B faster TTFT)
