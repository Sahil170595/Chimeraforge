# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 117.00s
- Sequential Estimate: 170.37s
- Speedup: 1.46x
- Efficiency: 72.8% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=2048, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 67.16 tok/s
- TTFT: 551.70 ms
- Total Duration: 116985.38 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=2048, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.49 tok/s
- TTFT: 809.95 ms
- Total Duration: 53348.06 ms

## Delta (B - A)
- Throughput Δ: -25.67 tok/s
- TTFT Δ: -258.24 ms (positive = Agent B faster TTFT)
