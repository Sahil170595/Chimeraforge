# Rust Multi-Agent Report - Run 4

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 14.39s
- Sequential Estimate: 21.14s
- Speedup: 1.47x
- Efficiency: 73.5% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Baseline Collector)
- Base URL: http://localhost:11434
- Config: Ollama defaults
- Throughput: 99.55 tok/s
- TTFT: 10386.34 ms
- Total Duration: 14387.55 ms

## Agent B (Chimera Insight)
- Base URL: http://localhost:11434
- Config: num_gpu=60, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 100.26 tok/s
- TTFT: 170.69 ms
- Total Duration: 6748.28 ms

## Delta (B - A)
- Throughput Δ: +0.71 tok/s
- TTFT Δ: +10215.65 ms (positive = Agent B faster TTFT)
