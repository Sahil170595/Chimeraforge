# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 36.95s
- Sequential Estimate: 36.95s
- Speedup: 1.00x
- Efficiency: 50.0% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 108.33 tok/s
- TTFT: 579.04 ms
- Total Duration: 25700.36 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 111.06 tok/s
- TTFT: 586.30 ms
- Total Duration: 11194.39 ms

## Delta (B - A)
- Throughput Δ: +2.73 tok/s
- TTFT Δ: -7.26 ms (positive = Agent B faster TTFT)
