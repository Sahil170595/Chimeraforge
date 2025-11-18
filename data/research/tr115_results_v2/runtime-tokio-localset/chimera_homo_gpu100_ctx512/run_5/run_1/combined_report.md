# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 54.99s
- Sequential Estimate: 108.53s
- Speedup: 1.97x
- Efficiency: 98.7% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=100, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.05 tok/s
- TTFT: 680.16 ms
- Total Duration: 53529.28 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=100, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 42.46 tok/s
- TTFT: 707.04 ms
- Total Duration: 54970.70 ms

## Delta (B - A)
- Throughput Δ: +1.41 tok/s
- TTFT Δ: -26.88 ms (positive = Agent B faster TTFT)
