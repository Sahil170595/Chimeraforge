# Rust Multi-Agent Report - Run 3

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 58.11s
- Sequential Estimate: 112.23s
- Speedup: 1.93x
- Efficiency: 96.6% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 45.77 tok/s
- TTFT: 672.53 ms
- Total Duration: 58072.97 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=512, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 40.98 tok/s
- TTFT: 675.16 ms
- Total Duration: 54093.77 ms

## Delta (B - A)
- Throughput Δ: -4.78 tok/s
- TTFT Δ: -2.63 ms (positive = Agent B faster TTFT)
