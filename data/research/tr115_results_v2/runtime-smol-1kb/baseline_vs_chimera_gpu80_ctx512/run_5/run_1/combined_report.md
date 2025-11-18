# Rust Multi-Agent Report - Run 1

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 57.65s
- Sequential Estimate: 113.01s
- Speedup: 1.96x
- Efficiency: 98.0% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Baseline Collector)
- Base URL: http://localhost:11434
- Config: Ollama defaults
- Throughput: 43.30 tok/s
- TTFT: 864.14 ms
- Total Duration: 57635.64 ms

## Agent B (Chimera Insight)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 40.75 tok/s
- TTFT: 1083.40 ms
- Total Duration: 55341.45 ms

## Delta (B - A)
- Throughput Δ: -2.55 tok/s
- TTFT Δ: -219.25 ms (positive = Agent B faster TTFT)
