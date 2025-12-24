# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 12.53s
- Sequential Estimate: 22.73s
- Speedup: 1.81x
- Efficiency: 90.7% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 40.85 tok/s
- TTFT: 672.95 ms
- Total Duration: 10194.98 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 54.61 tok/s
- TTFT: 581.54 ms
- Total Duration: 12530.85 ms

## Delta (B - A)
- Throughput Δ: +13.76 tok/s
- TTFT Δ: +91.41 ms (positive = Agent B faster TTFT)
