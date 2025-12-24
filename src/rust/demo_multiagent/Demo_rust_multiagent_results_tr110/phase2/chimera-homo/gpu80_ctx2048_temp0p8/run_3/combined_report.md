# Rust Multi-Agent Report - Run 3

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 10.63s
- Sequential Estimate: 14.72s
- Speedup: 1.38x
- Efficiency: 69.2% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=2048, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 100.42 tok/s
- TTFT: 210.04 ms
- Total Duration: 4085.74 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=2048, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 100.05 tok/s
- TTFT: 4116.44 ms
- Total Duration: 10629.35 ms

## Delta (B - A)
- Throughput Δ: -0.37 tok/s
- TTFT Δ: -3906.40 ms (positive = Agent B faster TTFT)
