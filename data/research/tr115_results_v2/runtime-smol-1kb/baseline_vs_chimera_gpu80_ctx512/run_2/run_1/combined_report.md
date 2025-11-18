# Rust Multi-Agent Report - Run 1

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 59.71s
- Sequential Estimate: 119.35s
- Speedup: 2.00x
- Efficiency: 99.9% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Baseline Collector)
- Base URL: http://localhost:11434
- Config: Ollama defaults
- Throughput: 40.87 tok/s
- TTFT: 1065.51 ms
- Total Duration: 59619.05 ms

## Agent B (Chimera Insight)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 40.77 tok/s
- TTFT: 1077.49 ms
- Total Duration: 59688.57 ms

## Delta (B - A)
- Throughput Δ: -0.11 tok/s
- TTFT Δ: -11.98 ms (positive = Agent B faster TTFT)
