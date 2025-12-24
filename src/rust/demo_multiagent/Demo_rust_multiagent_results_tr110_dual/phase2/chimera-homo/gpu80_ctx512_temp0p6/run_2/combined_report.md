# Rust Multi-Agent Report - Run 2

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 11.96s
- Sequential Estimate: 21.75s
- Speedup: 1.82x
- Efficiency: 90.9% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://127.0.0.1:11434
- Config: num_gpu=80, num_ctx=512, temp=0.6, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 41.17 tok/s
- TTFT: 253.44 ms
- Total Duration: 9786.31 ms

## Agent B (Chimera Agent B)
- Base URL: http://127.0.0.1:11435
- Config: num_gpu=80, num_ctx=512, temp=0.6, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 53.41 tok/s
- TTFT: 309.83 ms
- Total Duration: 11962.11 ms

## Delta (B - A)
- Throughput Δ: +12.24 tok/s
- TTFT Δ: -56.39 ms (positive = Agent B faster TTFT)
