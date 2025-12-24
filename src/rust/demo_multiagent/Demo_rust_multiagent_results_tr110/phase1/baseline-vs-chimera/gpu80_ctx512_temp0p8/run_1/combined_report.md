# Rust Multi-Agent Report - Run 1

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 14.97s
- Sequential Estimate: 18.75s
- Speedup: 1.25x
- Efficiency: 62.6% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Baseline Collector)
- Base URL: http://localhost:11434
- Config: Ollama defaults
- Throughput: 100.33 tok/s
- TTFT: 253.94 ms
- Total Duration: 3784.58 ms

## Agent B (Chimera Insight)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 99.43 tok/s
- TTFT: 7597.14 ms
- Total Duration: 14962.81 ms

## Delta (B - A)
- Throughput Δ: -0.90 tok/s
- TTFT Δ: -7343.21 ms (positive = Agent B faster TTFT)
