# Rust Multi-Agent Report - Run 4

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 12.55s
- Sequential Estimate: 22.26s
- Speedup: 1.77x
- Efficiency: 88.7% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Baseline Collector)
- Base URL: http://127.0.0.1:11434
- Config: Ollama defaults
- Throughput: 41.33 tok/s
- TTFT: 261.03 ms
- Total Duration: 9708.57 ms

## Agent B (Chimera Insight)
- Base URL: http://127.0.0.1:11435
- Config: num_gpu=80, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 57.11 tok/s
- TTFT: 309.56 ms
- Total Duration: 12553.27 ms

## Delta (B - A)
- Throughput Δ: +15.79 tok/s
- TTFT Δ: -48.54 ms (positive = Agent B faster TTFT)
