# Rust Multi-Agent Report - Run 1

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 70.87s
- Sequential Estimate: 141.10s
- Speedup: 1.99x
- Efficiency: 99.5% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Baseline Collector)
- Base URL: http://localhost:11434
- Config: Ollama defaults
- Throughput: 38.67 tok/s
- TTFT: 4802.74 ms
- Total Duration: 70852.03 ms

## Agent B (Chimera Insight)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 38.69 tok/s
- TTFT: 4795.62 ms
- Total Duration: 70208.13 ms

## Delta (B - A)
- Throughput Δ: +0.02 tok/s
- TTFT Δ: +7.12 ms (positive = Agent B faster TTFT)
