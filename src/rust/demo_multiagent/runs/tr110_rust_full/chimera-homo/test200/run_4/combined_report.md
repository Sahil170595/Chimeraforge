# Rust Multi-Agent Report - Run 4

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 58.26s
- Sequential Estimate: 116.30s
- Speedup: 2.00x
- Efficiency: 99.8% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.14 tok/s
- TTFT: 656.98 ms
- Total Duration: 58224.27 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=512, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 40.70 tok/s
- TTFT: 559.75 ms
- Total Duration: 58010.37 ms

## Delta (B - A)
- Throughput Δ: -0.44 tok/s
- TTFT Δ: +97.23 ms (positive = Agent B faster TTFT)
