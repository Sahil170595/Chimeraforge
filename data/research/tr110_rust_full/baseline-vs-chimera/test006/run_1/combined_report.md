# Rust Multi-Agent Report - Run 1

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 55.81s
- Sequential Estimate: 109.59s
- Speedup: 1.96x
- Efficiency: 98.2% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Baseline Collector)
- Base URL: http://localhost:11434
- Config: Ollama defaults
- Throughput: 43.52 tok/s
- TTFT: 788.35 ms
- Total Duration: 55773.88 ms

## Agent B (Chimera Insight)
- Base URL: http://localhost:11435
- Config: num_gpu=120, num_ctx=1024, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 40.85 tok/s
- TTFT: 826.13 ms
- Total Duration: 53757.91 ms

## Delta (B - A)
- Throughput Δ: -2.67 tok/s
- TTFT Δ: -37.78 ms (positive = Agent B faster TTFT)
