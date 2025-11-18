# Rust Multi-Agent Report - Run 1

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 56.29s
- Sequential Estimate: 109.72s
- Speedup: 1.95x
- Efficiency: 97.5% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Baseline Collector)
- Base URL: http://localhost:11434
- Config: Ollama defaults
- Throughput: 45.43 tok/s
- TTFT: 798.48 ms
- Total Duration: 56265.33 ms

## Agent B (Chimera Insight)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 42.51 tok/s
- TTFT: 841.22 ms
- Total Duration: 53417.72 ms

## Delta (B - A)
- Throughput Δ: -2.92 tok/s
- TTFT Δ: -42.74 ms (positive = Agent B faster TTFT)
