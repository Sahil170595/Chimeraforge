# Rust Multi-Agent Report - Run 3

## Scenario
- Type: chimera_hetero
- Concurrent Wall Time: 56.77s
- Sequential Estimate: 111.84s
- Speedup: 1.97x
- Efficiency: 98.5% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=60, num_ctx=512, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.24 tok/s
- TTFT: 657.30 ms
- Total Duration: 55039.68 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=1024, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 43.01 tok/s
- TTFT: 561.68 ms
- Total Duration: 56736.67 ms

## Delta (B - A)
- Throughput Δ: +1.77 tok/s
- TTFT Δ: +95.62 ms (positive = Agent B faster TTFT)
