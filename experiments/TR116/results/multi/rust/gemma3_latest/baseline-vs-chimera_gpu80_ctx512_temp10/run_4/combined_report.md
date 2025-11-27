# Rust Multi-Agent Report – Run 4

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 53.93s
- Sequential Estimate: 103.81s
- Speedup: 1.92x
- Efficiency: 96.2% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Baseline Collector)
- Base URL: http://localhost:11434
- Config: Ollama defaults
- Throughput: 46.24 tok/s
- TTFT: 630.38 ms
- Total Duration: 53934.08 ms

## Agent B (Chimera Insight)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.28 tok/s
- TTFT: 456.45 ms
- Total Duration: 49878.30 ms

## Delta (B - A)
- Throughput Δ: -4.96 tok/s
- TTFT Δ: +173.93 ms (positive = Agent B faster TTFT)
