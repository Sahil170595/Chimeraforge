# Rust Multi-Agent Report - Run 1

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 58.87s
- Sequential Estimate: 114.95s
- Speedup: 1.95x
- Efficiency: 97.6% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Baseline Collector)
- Base URL: http://localhost:11434
- Config: Ollama defaults
- Throughput: 49.95 tok/s
- TTFT: 749.46 ms
- Total Duration: 56040.85 ms

## Agent B (Chimera Insight)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=512, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 44.41 tok/s
- TTFT: 3078.07 ms
- Total Duration: 58836.18 ms

## Delta (B - A)
- Throughput Δ: -5.54 tok/s
- TTFT Δ: -2328.61 ms (positive = Agent B faster TTFT)
