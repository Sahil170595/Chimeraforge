# Rust Multi-Agent Report - Run 1

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 57.46s
- Sequential Estimate: 113.65s
- Speedup: 1.98x
- Efficiency: 98.9% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Baseline Collector)
- Base URL: http://localhost:11434
- Config: Ollama defaults
- Throughput: 47.30 tok/s
- TTFT: 799.23 ms
- Total Duration: 56161.11 ms

## Agent B (Chimera Insight)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=512, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 42.26 tok/s
- TTFT: 2535.19 ms
- Total Duration: 57425.85 ms

## Delta (B - A)
- Throughput Δ: -5.03 tok/s
- TTFT Δ: -1735.95 ms (positive = Agent B faster TTFT)
