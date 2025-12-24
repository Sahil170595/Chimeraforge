# Rust Multi-Agent Report - Run 1

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 57.41s
- Sequential Estimate: 111.75s
- Speedup: 1.95x
- Efficiency: 97.3% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Baseline Collector)
- Base URL: http://localhost:11434
- Config: Ollama defaults
- Throughput: 44.50 tok/s
- TTFT: 1069.34 ms
- Total Duration: 57392.96 ms

## Agent B (Chimera Insight)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 40.59 tok/s
- TTFT: 977.59 ms
- Total Duration: 54328.11 ms

## Delta (B - A)
- Throughput Δ: -3.91 tok/s
- TTFT Δ: +91.76 ms (positive = Agent B faster TTFT)
