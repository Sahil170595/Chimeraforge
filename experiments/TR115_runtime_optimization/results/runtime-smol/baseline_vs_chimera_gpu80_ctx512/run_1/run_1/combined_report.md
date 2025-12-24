# Rust Multi-Agent Report - Run 1

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 18.28s
- Sequential Estimate: 34.06s
- Speedup: 1.86x
- Efficiency: 93.2% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Baseline Collector)
- Base URL: http://localhost:11434
- Config: Ollama defaults
- Throughput: 42.67 tok/s
- TTFT: 6313.45 ms
- Total Duration: 15788.27 ms

## Agent B (Chimera Insight)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 58.29 tok/s
- TTFT: 6377.45 ms
- Total Duration: 18276.24 ms

## Delta (B - A)
- Throughput Δ: +15.62 tok/s
- TTFT Δ: -64.00 ms (positive = Agent B faster TTFT)
