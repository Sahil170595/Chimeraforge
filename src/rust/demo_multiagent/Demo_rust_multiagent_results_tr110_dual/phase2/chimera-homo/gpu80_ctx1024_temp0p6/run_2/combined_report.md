# Rust Multi-Agent Report - Run 2

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 12.23s
- Sequential Estimate: 22.31s
- Speedup: 1.82x
- Efficiency: 91.2% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://127.0.0.1:11434
- Config: num_gpu=80, num_ctx=1024, temp=0.6, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 41.01 tok/s
- TTFT: 273.97 ms
- Total Duration: 10078.75 ms

## Agent B (Chimera Agent B)
- Base URL: http://127.0.0.1:11435
- Config: num_gpu=80, num_ctx=1024, temp=0.6, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 53.12 tok/s
- TTFT: 300.69 ms
- Total Duration: 12228.51 ms

## Delta (B - A)
- Throughput Δ: +12.11 tok/s
- TTFT Δ: -26.72 ms (positive = Agent B faster TTFT)
