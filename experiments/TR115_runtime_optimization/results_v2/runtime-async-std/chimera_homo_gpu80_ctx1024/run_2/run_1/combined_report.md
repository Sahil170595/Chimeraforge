# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 44.12s
- Sequential Estimate: 44.12s
- Speedup: 1.00x
- Efficiency: 50.0% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=1024, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 108.49 tok/s
- TTFT: 567.82 ms
- Total Duration: 21176.44 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=1024, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 108.19 tok/s
- TTFT: 602.81 ms
- Total Duration: 22876.96 ms

## Delta (B - A)
- Throughput Δ: -0.30 tok/s
- TTFT Δ: -34.99 ms (positive = Agent B faster TTFT)
