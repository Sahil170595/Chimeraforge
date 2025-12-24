# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 50.91s
- Sequential Estimate: 96.51s
- Speedup: 1.90x
- Efficiency: 94.8% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 49.31 tok/s
- TTFT: 656.21 ms
- Total Duration: 45594.29 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 50.59 tok/s
- TTFT: 2874.36 ms
- Total Duration: 50890.27 ms

## Delta (B - A)
- Throughput Δ: +1.28 tok/s
- TTFT Δ: -2218.15 ms (positive = Agent B faster TTFT)
