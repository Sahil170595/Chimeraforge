# Rust Multi-Agent Report - Run 1

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 71.48s
- Sequential Estimate: 137.24s
- Speedup: 1.92x
- Efficiency: 96.0% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Baseline Collector)
- Base URL: http://localhost:11434
- Config: Ollama defaults
- Throughput: 46.36 tok/s
- TTFT: 4622.03 ms
- Total Duration: 71457.76 ms

## Agent B (Chimera Insight)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 40.74 tok/s
- TTFT: 4175.81 ms
- Total Duration: 65738.08 ms

## Delta (B - A)
- Throughput Δ: -5.62 tok/s
- TTFT Δ: +446.22 ms (positive = Agent B faster TTFT)
