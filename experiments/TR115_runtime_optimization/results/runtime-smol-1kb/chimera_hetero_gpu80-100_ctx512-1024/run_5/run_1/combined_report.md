# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_hetero
- Concurrent Wall Time: 5.06s
- Sequential Estimate: 7.14s
- Speedup: 1.41x
- Efficiency: 70.6% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 96.83 tok/s
- TTFT: 896.75 ms
- Total Duration: 5060.62 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=100, num_ctx=1024, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 48.44 tok/s
- TTFT: 671.75 ms
- Total Duration: 2083.34 ms

## Delta (B - A)
- Throughput Δ: -48.39 tok/s
- TTFT Δ: +225.01 ms (positive = Agent B faster TTFT)
