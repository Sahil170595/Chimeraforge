# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 46.34s
- Sequential Estimate: 46.34s
- Speedup: 1.00x
- Efficiency: 50.0% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 109.06 tok/s
- TTFT: 589.38 ms
- Total Duration: 23444.17 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 108.11 tok/s
- TTFT: 589.90 ms
- Total Duration: 22833.17 ms

## Delta (B - A)
- Throughput Δ: -0.94 tok/s
- TTFT Δ: -0.52 ms (positive = Agent B faster TTFT)
