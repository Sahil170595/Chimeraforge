# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 53.23s
- Sequential Estimate: 104.00s
- Speedup: 1.95x
- Efficiency: 97.7% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=100, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 42.88 tok/s
- TTFT: 767.00 ms
- Total Duration: 50751.24 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=100, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 46.09 tok/s
- TTFT: 800.83 ms
- Total Duration: 53195.73 ms

## Delta (B - A)
- Throughput Δ: +3.21 tok/s
- TTFT Δ: -33.83 ms (positive = Agent B faster TTFT)
