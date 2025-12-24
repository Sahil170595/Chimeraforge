# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 49.82s
- Sequential Estimate: 49.81s
- Speedup: 1.00x
- Efficiency: 50.0% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=2048, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 108.08 tok/s
- TTFT: 581.46 ms
- Total Duration: 24334.46 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=2048, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 107.61 tok/s
- TTFT: 583.00 ms
- Total Duration: 25411.05 ms

## Delta (B - A)
- Throughput Δ: -0.47 tok/s
- TTFT Δ: -1.54 ms (positive = Agent B faster TTFT)
