# Rust Multi-Agent Report - Run 1

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 63.37s
- Sequential Estimate: 120.85s
- Speedup: 1.91x
- Efficiency: 95.4% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Baseline Collector)
- Base URL: http://localhost:11434
- Config: Ollama defaults
- Throughput: 46.40 tok/s
- TTFT: 814.32 ms
- Total Duration: 63347.65 ms

## Agent B (Chimera Insight)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 40.60 tok/s
- TTFT: 805.39 ms
- Total Duration: 57455.07 ms

## Delta (B - A)
- Throughput Δ: -5.80 tok/s
- TTFT Δ: +8.92 ms (positive = Agent B faster TTFT)
