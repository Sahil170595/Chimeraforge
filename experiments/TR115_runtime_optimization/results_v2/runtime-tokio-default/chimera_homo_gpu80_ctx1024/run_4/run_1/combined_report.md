# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 56.04s
- Sequential Estimate: 111.20s
- Speedup: 1.98x
- Efficiency: 99.2% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=1024, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.19 tok/s
- TTFT: 776.62 ms
- Total Duration: 55124.60 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=1024, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 42.15 tok/s
- TTFT: 819.72 ms
- Total Duration: 56013.33 ms

## Delta (B - A)
- Throughput Δ: +0.96 tok/s
- TTFT Δ: -43.11 ms (positive = Agent B faster TTFT)
