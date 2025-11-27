# Rust Multi-Agent Report – Run 5

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 83.65s
- Sequential Estimate: 135.84s
- Speedup: 1.62x
- Efficiency: 81.2% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Baseline Collector)
- Base URL: http://localhost:11434
- Config: Ollama defaults
- Throughput: 24.05 tok/s
- TTFT: 270.54 ms
- Total Duration: 52190.91 ms

## Agent B (Chimera Insight)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 38.37 tok/s
- TTFT: 220.75 ms
- Total Duration: 83646.11 ms

## Delta (B - A)
- Throughput Δ: +14.33 tok/s
- TTFT Δ: +49.78 ms (positive = Agent B faster TTFT)
