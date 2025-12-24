# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 10.14s
- Sequential Estimate: 10.14s
- Speedup: 1.00x
- Efficiency: 50.0% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 123.69 tok/s
- TTFT: 847.75 ms
- Total Duration: 4057.52 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 121.48 tok/s
- TTFT: 598.70 ms
- Total Duration: 6083.73 ms

## Delta (B - A)
- Throughput Δ: -2.20 tok/s
- TTFT Δ: +249.05 ms (positive = Agent B faster TTFT)
