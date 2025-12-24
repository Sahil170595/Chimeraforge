# Rust Multi-Agent Report - Run 1

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 47.38s
- Sequential Estimate: 47.37s
- Speedup: 1.00x
- Efficiency: 50.0% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Baseline Collector)
- Base URL: http://localhost:11434
- Config: Ollama defaults
- Throughput: 115.78 tok/s
- TTFT: 643.11 ms
- Total Duration: 24518.57 ms

## Agent B (Chimera Insight)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 111.23 tok/s
- TTFT: 611.87 ms
- Total Duration: 22795.13 ms

## Delta (B - A)
- Throughput Δ: -4.55 tok/s
- TTFT Δ: +31.24 ms (positive = Agent B faster TTFT)
