# Rust Multi-Agent Report - Run 4

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 55.52s
- Sequential Estimate: 109.45s
- Speedup: 1.97x
- Efficiency: 98.6% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=1024, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 40.55 tok/s
- TTFT: 685.58 ms
- Total Duration: 53884.16 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=1024, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 42.07 tok/s
- TTFT: 582.65 ms
- Total Duration: 55474.43 ms

## Delta (B - A)
- Throughput Δ: +1.52 tok/s
- TTFT Δ: +102.93 ms (positive = Agent B faster TTFT)
