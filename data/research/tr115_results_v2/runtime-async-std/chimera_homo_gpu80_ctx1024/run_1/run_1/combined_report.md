# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 43.44s
- Sequential Estimate: 43.44s
- Speedup: 1.00x
- Efficiency: 50.0% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=1024, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 108.49 tok/s
- TTFT: 591.17 ms
- Total Duration: 19056.18 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=1024, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 108.75 tok/s
- TTFT: 575.14 ms
- Total Duration: 24321.70 ms

## Delta (B - A)
- Throughput Δ: +0.25 tok/s
- TTFT Δ: +16.02 ms (positive = Agent B faster TTFT)
