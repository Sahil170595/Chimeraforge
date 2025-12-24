# Rust Multi-Agent Report - Run 1

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 12.76s
- Sequential Estimate: 23.48s
- Speedup: 1.84x
- Efficiency: 92.1% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Baseline Collector)
- Base URL: http://localhost:11434
- Config: Ollama defaults
- Throughput: 39.01 tok/s
- TTFT: 829.29 ms
- Total Duration: 10727.83 ms

## Agent B (Chimera Insight)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 51.84 tok/s
- TTFT: 595.98 ms
- Total Duration: 12755.16 ms

## Delta (B - A)
- Throughput Δ: +12.83 tok/s
- TTFT Δ: +233.31 ms (positive = Agent B faster TTFT)
