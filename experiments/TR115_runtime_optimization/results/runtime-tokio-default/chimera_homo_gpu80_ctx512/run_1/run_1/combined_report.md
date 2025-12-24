# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 12.48s
- Sequential Estimate: 17.08s
- Speedup: 1.37x
- Efficiency: 68.4% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 105.23 tok/s
- TTFT: 777.66 ms
- Total Duration: 4603.95 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 112.90 tok/s
- TTFT: 5810.22 ms
- Total Duration: 12480.71 ms

## Delta (B - A)
- Throughput Δ: +7.67 tok/s
- TTFT Δ: -5032.57 ms (positive = Agent B faster TTFT)
