# Rust Multi-Agent Report - Run 3

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 12.80s
- Sequential Estimate: 23.23s
- Speedup: 1.82x
- Efficiency: 90.8% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Baseline Collector)
- Base URL: http://127.0.0.1:11434
- Config: Ollama defaults
- Throughput: 41.09 tok/s
- TTFT: 300.56 ms
- Total Duration: 10431.83 ms

## Agent B (Chimera Insight)
- Base URL: http://127.0.0.1:11435
- Config: num_gpu=80, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 53.98 tok/s
- TTFT: 309.22 ms
- Total Duration: 12795.62 ms

## Delta (B - A)
- Throughput Δ: +12.89 tok/s
- TTFT Δ: -8.65 ms (positive = Agent B faster TTFT)
