# Rust Multi-Agent Report - Run 1

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 62.47s
- Sequential Estimate: 124.77s
- Speedup: 2.00x
- Efficiency: 99.9% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Baseline Collector)
- Base URL: http://localhost:11434
- Config: Ollama defaults
- Throughput: 42.96 tok/s
- TTFT: 4851.66 ms
- Total Duration: 62445.79 ms

## Agent B (Chimera Insight)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 42.67 tok/s
- TTFT: 4746.60 ms
- Total Duration: 62283.09 ms

## Delta (B - A)
- Throughput Δ: -0.29 tok/s
- TTFT Δ: +105.06 ms (positive = Agent B faster TTFT)
