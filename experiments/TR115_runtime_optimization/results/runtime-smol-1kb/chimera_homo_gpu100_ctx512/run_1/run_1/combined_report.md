# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 19.52s
- Sequential Estimate: 35.38s
- Speedup: 1.81x
- Efficiency: 90.6% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=100, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 44.04 tok/s
- TTFT: 7434.33 ms
- Total Duration: 15855.17 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=100, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 65.54 tok/s
- TTFT: 7820.49 ms
- Total Duration: 19520.60 ms

## Delta (B - A)
- Throughput Δ: +21.50 tok/s
- TTFT Δ: -386.16 ms (positive = Agent B faster TTFT)
