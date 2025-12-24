# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 10.55s
- Sequential Estimate: 10.55s
- Speedup: 1.00x
- Efficiency: 50.0% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 123.07 tok/s
- TTFT: 873.42 ms
- Total Duration: 4409.27 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 121.88 tok/s
- TTFT: 603.48 ms
- Total Duration: 6137.50 ms

## Delta (B - A)
- Throughput Δ: -1.19 tok/s
- TTFT Δ: +269.93 ms (positive = Agent B faster TTFT)
