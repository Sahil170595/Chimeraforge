# Rust Multi-Agent Report – Run 3

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 55.92s
- Sequential Estimate: 107.04s
- Speedup: 1.91x
- Efficiency: 95.7% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Baseline Collector)
- Base URL: http://localhost:11434
- Config: Ollama defaults
- Throughput: 46.60 tok/s
- TTFT: 559.31 ms
- Total Duration: 55923.87 ms

## Agent B (Chimera Insight)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 40.85 tok/s
- TTFT: 442.90 ms
- Total Duration: 51112.86 ms

## Delta (B - A)
- Throughput Δ: -5.75 tok/s
- TTFT Δ: +116.41 ms (positive = Agent B faster TTFT)
