# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 57.98s
- Sequential Estimate: 115.91s
- Speedup: 2.00x
- Efficiency: 99.9% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=1024, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 40.70 tok/s
- TTFT: 517.19 ms
- Total Duration: 57908.56 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=1024, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 40.91 tok/s
- TTFT: 819.52 ms
- Total Duration: 57965.76 ms

## Delta (B - A)
- Throughput Δ: +0.21 tok/s
- TTFT Δ: -302.33 ms (positive = Agent B faster TTFT)
