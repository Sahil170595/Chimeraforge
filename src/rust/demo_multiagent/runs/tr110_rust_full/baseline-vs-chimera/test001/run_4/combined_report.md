# Rust Multi-Agent Report - Run 4

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 60.22s
- Sequential Estimate: 117.55s
- Speedup: 1.95x
- Efficiency: 97.6% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Baseline Collector)
- Base URL: http://localhost:11434
- Config: Ollama defaults
- Throughput: 43.07 tok/s
- TTFT: 804.67 ms
- Total Duration: 60189.50 ms

## Agent B (Chimera Insight)
- Base URL: http://localhost:11435
- Config: num_gpu=60, num_ctx=512, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 40.23 tok/s
- TTFT: 663.40 ms
- Total Duration: 57289.14 ms

## Delta (B - A)
- Throughput Δ: -2.84 tok/s
- TTFT Δ: +141.27 ms (positive = Agent B faster TTFT)
