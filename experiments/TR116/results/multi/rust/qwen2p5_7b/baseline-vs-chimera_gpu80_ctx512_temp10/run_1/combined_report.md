# Rust Multi-Agent Report – Run 1

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 84.69s
- Sequential Estimate: 144.11s
- Speedup: 1.70x
- Efficiency: 85.1% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Baseline Collector)
- Base URL: http://localhost:11434
- Config: Ollama defaults
- Throughput: 23.98 tok/s
- TTFT: 1763.68 ms
- Total Duration: 59416.58 ms

## Agent B (Chimera Insight)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 54.45 tok/s
- TTFT: 340.91 ms
- Total Duration: 84693.87 ms

## Delta (B - A)
- Throughput Δ: +30.47 tok/s
- TTFT Δ: +1422.77 ms (positive = Agent B faster TTFT)
