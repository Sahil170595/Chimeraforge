# Rust Multi-Agent Report – Run 3

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 26.71s
- Sequential Estimate: 50.84s
- Speedup: 1.90x
- Efficiency: 95.2% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Baseline Collector)
- Base URL: http://localhost:11434
- Config: Ollama defaults
- Throughput: 31.55 tok/s
- TTFT: 407.45 ms
- Total Duration: 26708.31 ms

## Agent B (Chimera Insight)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 26.20 tok/s
- TTFT: 279.36 ms
- Total Duration: 24128.99 ms

## Delta (B - A)
- Throughput Δ: -5.35 tok/s
- TTFT Δ: +128.09 ms (positive = Agent B faster TTFT)
