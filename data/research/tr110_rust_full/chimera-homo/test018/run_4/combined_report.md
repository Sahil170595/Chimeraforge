# Rust Multi-Agent Report - Run 4

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 56.08s
- Sequential Estimate: 111.42s
- Speedup: 1.99x
- Efficiency: 99.3% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=120, num_ctx=1024, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 40.80 tok/s
- TTFT: 595.44 ms
- Total Duration: 55311.16 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=120, num_ctx=1024, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.81 tok/s
- TTFT: 658.76 ms
- Total Duration: 56046.57 ms

## Delta (B - A)
- Throughput Δ: +1.00 tok/s
- TTFT Δ: -63.32 ms (positive = Agent B faster TTFT)
