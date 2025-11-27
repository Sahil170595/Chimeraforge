# Rust Multi-Agent Report – Run 4

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 55.31s
- Sequential Estimate: 109.27s
- Speedup: 1.98x
- Efficiency: 98.8% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Baseline Collector)
- Base URL: http://localhost:11434
- Config: Ollama defaults
- Throughput: 25.20 tok/s
- TTFT: 309.57 ms
- Total Duration: 55307.07 ms

## Agent B (Chimera Insight)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 12.07 tok/s
- TTFT: 222.70 ms
- Total Duration: 53966.66 ms

## Delta (B - A)
- Throughput Δ: -13.13 tok/s
- TTFT Δ: +86.87 ms (positive = Agent B faster TTFT)
