# Rust Multi-Agent Report - Run 1

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 62.32s
- Sequential Estimate: 122.28s
- Speedup: 1.96x
- Efficiency: 98.1% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Baseline Collector)
- Base URL: http://localhost:11434
- Config: Ollama defaults
- Throughput: 43.61 tok/s
- TTFT: 1008.93 ms
- Total Duration: 62237.52 ms

## Agent B (Chimera Insight)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.15 tok/s
- TTFT: 842.45 ms
- Total Duration: 59884.87 ms

## Delta (B - A)
- Throughput Δ: -2.46 tok/s
- TTFT Δ: +166.48 ms (positive = Agent B faster TTFT)
