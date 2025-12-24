# Rust Multi-Agent Report - Run 1

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 12.45s
- Sequential Estimate: 23.12s
- Speedup: 1.86x
- Efficiency: 92.9% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Baseline Collector)
- Base URL: http://localhost:11434
- Config: Ollama defaults
- Throughput: 42.29 tok/s
- TTFT: 891.43 ms
- Total Duration: 10675.13 ms

## Agent B (Chimera Insight)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 53.91 tok/s
- TTFT: 695.01 ms
- Total Duration: 12448.33 ms

## Delta (B - A)
- Throughput Δ: +11.62 tok/s
- TTFT Δ: +196.43 ms (positive = Agent B faster TTFT)
