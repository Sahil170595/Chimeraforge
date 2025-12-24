# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 10.32s
- Sequential Estimate: 10.32s
- Speedup: 1.00x
- Efficiency: 50.0% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=100, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 123.10 tok/s
- TTFT: 834.97 ms
- Total Duration: 4286.24 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=100, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 121.95 tok/s
- TTFT: 600.59 ms
- Total Duration: 6031.62 ms

## Delta (B - A)
- Throughput Δ: -1.16 tok/s
- TTFT Δ: +234.39 ms (positive = Agent B faster TTFT)
