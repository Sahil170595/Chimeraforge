# Rust Multi-Agent Report - Run 1

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 5.37s
- Sequential Estimate: 7.91s
- Speedup: 1.47x
- Efficiency: 73.7% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Baseline Collector)
- Base URL: http://localhost:11434
- Config: Ollama defaults
- Throughput: 84.79 tok/s
- TTFT: 694.99 ms
- Total Duration: 5365.72 ms

## Agent B (Chimera Insight)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 43.92 tok/s
- TTFT: 610.33 ms
- Total Duration: 2544.70 ms

## Delta (B - A)
- Throughput Δ: -40.87 tok/s
- TTFT Δ: +84.66 ms (positive = Agent B faster TTFT)
