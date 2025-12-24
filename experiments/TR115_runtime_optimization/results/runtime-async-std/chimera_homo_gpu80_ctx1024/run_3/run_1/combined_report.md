# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 9.76s
- Sequential Estimate: 9.76s
- Speedup: 1.00x
- Efficiency: 50.0% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=1024, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 123.54 tok/s
- TTFT: 902.08 ms
- Total Duration: 4151.61 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=1024, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 121.84 tok/s
- TTFT: 577.86 ms
- Total Duration: 5608.16 ms

## Delta (B - A)
- Throughput Δ: -1.70 tok/s
- TTFT Δ: +324.22 ms (positive = Agent B faster TTFT)
