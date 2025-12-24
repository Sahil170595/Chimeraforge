# Rust Multi-Agent Report - Run 1

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 12.65s
- Sequential Estimate: 22.51s
- Speedup: 1.78x
- Efficiency: 88.9% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Baseline Collector)
- Base URL: http://localhost:11434
- Config: Ollama defaults
- Throughput: 41.05 tok/s
- TTFT: 775.76 ms
- Total Duration: 9853.43 ms

## Agent B (Chimera Insight)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 57.55 tok/s
- TTFT: 628.50 ms
- Total Duration: 12653.32 ms

## Delta (B - A)
- Throughput Δ: +16.51 tok/s
- TTFT Δ: +147.27 ms (positive = Agent B faster TTFT)
