# Rust Multi-Agent Report - Run 1

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 19.23s
- Sequential Estimate: 29.63s
- Speedup: 1.54x
- Efficiency: 77.0% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Baseline Collector)
- Base URL: http://localhost:11434
- Config: Ollama defaults
- Throughput: 98.24 tok/s
- TTFT: 14553.81 ms
- Total Duration: 19232.30 ms

## Agent B (Chimera Insight)
- Base URL: http://localhost:11434
- Config: num_gpu=60, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 99.09 tok/s
- TTFT: 3724.50 ms
- Total Duration: 10394.32 ms

## Delta (B - A)
- Throughput Δ: +0.85 tok/s
- TTFT Δ: +10829.31 ms (positive = Agent B faster TTFT)
