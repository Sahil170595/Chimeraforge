# Rust Multi-Agent Report - Run 4

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 58.49s
- Sequential Estimate: 113.89s
- Speedup: 1.95x
- Efficiency: 97.4% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Baseline Collector)
- Base URL: http://localhost:11434
- Config: Ollama defaults
- Throughput: 44.35 tok/s
- TTFT: 833.30 ms
- Total Duration: 58459.21 ms

## Agent B (Chimera Insight)
- Base URL: http://localhost:11435
- Config: num_gpu=120, num_ctx=1024, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.00 tok/s
- TTFT: 682.48 ms
- Total Duration: 55379.34 ms

## Delta (B - A)
- Throughput Δ: -3.35 tok/s
- TTFT Δ: +150.82 ms (positive = Agent B faster TTFT)
