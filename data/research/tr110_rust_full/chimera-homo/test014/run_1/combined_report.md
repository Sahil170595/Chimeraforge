# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 52.17s
- Sequential Estimate: 104.11s
- Speedup: 2.00x
- Efficiency: 99.8% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=60, num_ctx=1024, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.60 tok/s
- TTFT: 545.59 ms
- Total Duration: 52128.53 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=60, num_ctx=1024, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.08 tok/s
- TTFT: 815.98 ms
- Total Duration: 51911.07 ms

## Delta (B - A)
- Throughput Δ: -0.51 tok/s
- TTFT Δ: -270.39 ms (positive = Agent B faster TTFT)
