# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_hetero
- Concurrent Wall Time: 47.63s
- Sequential Estimate: 47.62s
- Speedup: 1.00x
- Efficiency: 50.0% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 108.30 tok/s
- TTFT: 595.71 ms
- Total Duration: 24686.10 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=100, num_ctx=1024, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 108.26 tok/s
- TTFT: 593.91 ms
- Total Duration: 22870.28 ms

## Delta (B - A)
- Throughput Δ: -0.04 tok/s
- TTFT Δ: +1.80 ms (positive = Agent B faster TTFT)
