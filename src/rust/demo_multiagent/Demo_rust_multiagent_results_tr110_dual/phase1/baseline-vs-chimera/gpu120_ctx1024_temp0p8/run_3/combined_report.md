# Rust Multi-Agent Report - Run 3

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 5.60s
- Sequential Estimate: 7.87s
- Speedup: 1.41x
- Efficiency: 70.3% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Baseline Collector)
- Base URL: http://127.0.0.1:11434
- Config: Ollama defaults
- Throughput: 86.34 tok/s
- TTFT: 273.32 ms
- Total Duration: 5597.57 ms

## Agent B (Chimera Insight)
- Base URL: http://127.0.0.1:11435
- Config: num_gpu=120, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 42.19 tok/s
- TTFT: 291.43 ms
- Total Duration: 2276.92 ms

## Delta (B - A)
- Throughput Δ: -44.15 tok/s
- TTFT Δ: -18.11 ms (positive = Agent B faster TTFT)
