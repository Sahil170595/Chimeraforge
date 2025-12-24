# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 12.76s
- Sequential Estimate: 23.45s
- Speedup: 1.84x
- Efficiency: 91.9% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 42.84 tok/s
- TTFT: 962.62 ms
- Total Duration: 10687.99 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 55.93 tok/s
- TTFT: 676.59 ms
- Total Duration: 12761.13 ms

## Delta (B - A)
- Throughput Δ: +13.09 tok/s
- TTFT Δ: +286.03 ms (positive = Agent B faster TTFT)
