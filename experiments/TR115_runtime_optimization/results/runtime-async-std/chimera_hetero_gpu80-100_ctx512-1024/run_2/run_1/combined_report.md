# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_hetero
- Concurrent Wall Time: 10.28s
- Sequential Estimate: 10.28s
- Speedup: 1.00x
- Efficiency: 50.0% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 123.60 tok/s
- TTFT: 864.12 ms
- Total Duration: 4193.37 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=100, num_ctx=1024, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 121.55 tok/s
- TTFT: 605.16 ms
- Total Duration: 6086.17 ms

## Delta (B - A)
- Throughput Δ: -2.05 tok/s
- TTFT Δ: +258.97 ms (positive = Agent B faster TTFT)
