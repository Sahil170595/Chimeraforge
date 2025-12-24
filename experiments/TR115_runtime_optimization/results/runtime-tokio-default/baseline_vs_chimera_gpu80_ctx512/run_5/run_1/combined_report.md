# Rust Multi-Agent Report - Run 1

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 12.63s
- Sequential Estimate: 22.60s
- Speedup: 1.79x
- Efficiency: 89.4% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Baseline Collector)
- Base URL: http://localhost:11434
- Config: Ollama defaults
- Throughput: 38.98 tok/s
- TTFT: 786.12 ms
- Total Duration: 9961.91 ms

## Agent B (Chimera Insight)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 55.53 tok/s
- TTFT: 612.45 ms
- Total Duration: 12633.72 ms

## Delta (B - A)
- Throughput Δ: +16.55 tok/s
- TTFT Δ: +173.67 ms (positive = Agent B faster TTFT)
