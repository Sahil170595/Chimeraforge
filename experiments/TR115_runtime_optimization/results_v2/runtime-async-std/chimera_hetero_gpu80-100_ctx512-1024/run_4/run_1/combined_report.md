# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_hetero
- Concurrent Wall Time: 46.92s
- Sequential Estimate: 46.92s
- Speedup: 1.00x
- Efficiency: 50.0% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 108.46 tok/s
- TTFT: 585.72 ms
- Total Duration: 23100.89 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=100, num_ctx=1024, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 108.04 tok/s
- TTFT: 594.47 ms
- Total Duration: 23765.41 ms

## Delta (B - A)
- Throughput Δ: -0.42 tok/s
- TTFT Δ: -8.76 ms (positive = Agent B faster TTFT)
