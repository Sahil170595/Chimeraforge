# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 13.51s
- Sequential Estimate: 24.75s
- Speedup: 1.83x
- Efficiency: 91.6% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=100, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 40.42 tok/s
- TTFT: 729.28 ms
- Total Duration: 11238.34 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=100, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 53.10 tok/s
- TTFT: 618.11 ms
- Total Duration: 13508.55 ms

## Delta (B - A)
- Throughput Δ: +12.68 tok/s
- TTFT Δ: +111.16 ms (positive = Agent B faster TTFT)
