# Rust Multi-Agent Report - Run 5

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 17.34s
- Sequential Estimate: 27.41s
- Speedup: 1.58x
- Efficiency: 79.0% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Baseline Collector)
- Base URL: http://localhost:11434
- Config: Ollama defaults
- Throughput: 99.39 tok/s
- TTFT: 13399.11 ms
- Total Duration: 17342.88 ms

## Agent B (Chimera Insight)
- Base URL: http://localhost:11434
- Config: num_gpu=60, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 98.90 tok/s
- TTFT: 3540.57 ms
- Total Duration: 10063.49 ms

## Delta (B - A)
- Throughput Δ: -0.49 tok/s
- TTFT Δ: +9858.54 ms (positive = Agent B faster TTFT)
