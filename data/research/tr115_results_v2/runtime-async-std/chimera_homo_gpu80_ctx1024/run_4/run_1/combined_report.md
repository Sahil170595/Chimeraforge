# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 49.25s
- Sequential Estimate: 49.25s
- Speedup: 1.00x
- Efficiency: 50.0% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=1024, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 108.54 tok/s
- TTFT: 611.59 ms
- Total Duration: 24019.71 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=1024, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 108.09 tok/s
- TTFT: 586.06 ms
- Total Duration: 25160.01 ms

## Delta (B - A)
- Throughput Δ: -0.46 tok/s
- TTFT Δ: +25.53 ms (positive = Agent B faster TTFT)
