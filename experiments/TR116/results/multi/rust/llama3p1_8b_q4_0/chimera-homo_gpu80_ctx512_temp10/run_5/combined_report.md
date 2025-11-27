# Rust Multi-Agent Report – Run 5

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 29.36s
- Sequential Estimate: 57.76s
- Speedup: 1.97x
- Efficiency: 98.4% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 27.50 tok/s
- TTFT: 366.87 ms
- Total Duration: 29360.21 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 25.92 tok/s
- TTFT: 287.93 ms
- Total Duration: 28397.95 ms

## Delta (B - A)
- Throughput Δ: -1.57 tok/s
- TTFT Δ: +78.94 ms (positive = Agent B faster TTFT)
