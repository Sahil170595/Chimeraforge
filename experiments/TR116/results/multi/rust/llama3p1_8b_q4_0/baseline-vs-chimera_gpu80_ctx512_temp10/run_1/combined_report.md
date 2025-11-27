# Rust Multi-Agent Report – Run 1

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 31.62s
- Sequential Estimate: 60.82s
- Speedup: 1.92x
- Efficiency: 96.2% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Baseline Collector)
- Base URL: http://localhost:11434
- Config: Ollama defaults
- Throughput: 30.27 tok/s
- TTFT: 1893.42 ms
- Total Duration: 31618.99 ms

## Agent B (Chimera Insight)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 34.60 tok/s
- TTFT: 452.36 ms
- Total Duration: 29201.29 ms

## Delta (B - A)
- Throughput Δ: +4.33 tok/s
- TTFT Δ: +1441.06 ms (positive = Agent B faster TTFT)
