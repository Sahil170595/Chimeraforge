# Rust Multi-Agent Report - Run 5

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 59.91s
- Sequential Estimate: 118.68s
- Speedup: 1.98x
- Efficiency: 99.0% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=1024, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 42.32 tok/s
- TTFT: 659.11 ms
- Total Duration: 59882.20 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=1024, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 40.97 tok/s
- TTFT: 660.46 ms
- Total Duration: 58734.98 ms

## Delta (B - A)
- Throughput Δ: -1.35 tok/s
- TTFT Δ: -1.35 ms (positive = Agent B faster TTFT)
