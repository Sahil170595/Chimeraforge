# Rust Multi-Agent Report - Run 1

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 56.58s
- Sequential Estimate: 109.48s
- Speedup: 1.93x
- Efficiency: 96.7% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Baseline Collector)
- Base URL: http://localhost:11434
- Config: Ollama defaults
- Throughput: 45.29 tok/s
- TTFT: 913.60 ms
- Total Duration: 56564.50 ms

## Agent B (Chimera Insight)
- Base URL: http://localhost:11435
- Config: num_gpu=60, num_ctx=512, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 40.22 tok/s
- TTFT: 753.04 ms
- Total Duration: 52885.09 ms

## Delta (B - A)
- Throughput Δ: -5.07 tok/s
- TTFT Δ: +160.56 ms (positive = Agent B faster TTFT)
