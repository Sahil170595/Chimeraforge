# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 44.80s
- Sequential Estimate: 44.79s
- Speedup: 1.00x
- Efficiency: 50.0% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=1024, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 108.21 tok/s
- TTFT: 597.16 ms
- Total Duration: 22875.83 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=1024, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 54.49 tok/s
- TTFT: 589.67 ms
- Total Duration: 21855.77 ms

## Delta (B - A)
- Throughput Δ: -53.72 tok/s
- TTFT Δ: +7.48 ms (positive = Agent B faster TTFT)
