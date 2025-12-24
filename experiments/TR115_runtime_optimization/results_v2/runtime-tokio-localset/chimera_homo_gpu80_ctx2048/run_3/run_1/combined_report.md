# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 56.46s
- Sequential Estimate: 112.55s
- Speedup: 1.99x
- Efficiency: 99.7% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=2048, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 40.72 tok/s
- TTFT: 713.67 ms
- Total Duration: 56059.88 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=2048, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.45 tok/s
- TTFT: 814.05 ms
- Total Duration: 56429.30 ms

## Delta (B - A)
- Throughput Δ: +0.73 tok/s
- TTFT Δ: -100.38 ms (positive = Agent B faster TTFT)
