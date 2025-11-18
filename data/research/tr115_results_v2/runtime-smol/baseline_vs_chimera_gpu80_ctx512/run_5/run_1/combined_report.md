# Rust Multi-Agent Report - Run 1

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 58.74s
- Sequential Estimate: 115.15s
- Speedup: 1.96x
- Efficiency: 98.0% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Baseline Collector)
- Base URL: http://localhost:11434
- Config: Ollama defaults
- Throughput: 44.59 tok/s
- TTFT: 977.12 ms
- Total Duration: 58708.44 ms

## Agent B (Chimera Insight)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 42.48 tok/s
- TTFT: 851.16 ms
- Total Duration: 56376.59 ms

## Delta (B - A)
- Throughput Δ: -2.10 tok/s
- TTFT Δ: +125.96 ms (positive = Agent B faster TTFT)
