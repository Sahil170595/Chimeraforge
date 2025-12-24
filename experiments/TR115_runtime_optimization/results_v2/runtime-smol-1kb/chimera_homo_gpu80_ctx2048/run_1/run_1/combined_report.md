# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 52.98s
- Sequential Estimate: 105.37s
- Speedup: 1.99x
- Efficiency: 99.4% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=2048, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 40.78 tok/s
- TTFT: 870.58 ms
- Total Duration: 52354.48 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=2048, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.92 tok/s
- TTFT: 1060.84 ms
- Total Duration: 52944.71 ms

## Delta (B - A)
- Throughput Δ: +1.14 tok/s
- TTFT Δ: -190.26 ms (positive = Agent B faster TTFT)
