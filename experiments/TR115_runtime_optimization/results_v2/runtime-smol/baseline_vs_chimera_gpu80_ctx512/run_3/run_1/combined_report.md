# Rust Multi-Agent Report - Run 1

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 58.38s
- Sequential Estimate: 114.33s
- Speedup: 1.96x
- Efficiency: 97.9% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Baseline Collector)
- Base URL: http://localhost:11434
- Config: Ollama defaults
- Throughput: 45.09 tok/s
- TTFT: 871.05 ms
- Total Duration: 58360.41 ms

## Agent B (Chimera Insight)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 42.35 tok/s
- TTFT: 869.49 ms
- Total Duration: 55924.48 ms

## Delta (B - A)
- Throughput Δ: -2.74 tok/s
- TTFT Δ: +1.56 ms (positive = Agent B faster TTFT)
