# Rust Multi-Agent Report - Run 1

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 5.18s
- Sequential Estimate: 7.51s
- Speedup: 1.45x
- Efficiency: 72.5% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Baseline Collector)
- Base URL: http://localhost:11434
- Config: Ollama defaults
- Throughput: 86.44 tok/s
- TTFT: 684.21 ms
- Total Duration: 5175.05 ms

## Agent B (Chimera Insight)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 44.88 tok/s
- TTFT: 582.18 ms
- Total Duration: 2332.86 ms

## Delta (B - A)
- Throughput Δ: -41.56 tok/s
- TTFT Δ: +102.03 ms (positive = Agent B faster TTFT)
