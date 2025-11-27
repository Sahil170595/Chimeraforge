# Rust Multi-Agent Report – Run 4

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 31.58s
- Sequential Estimate: 60.32s
- Speedup: 1.91x
- Efficiency: 95.5% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Baseline Collector)
- Base URL: http://localhost:11434
- Config: Ollama defaults
- Throughput: 30.19 tok/s
- TTFT: 403.96 ms
- Total Duration: 31579.83 ms

## Agent B (Chimera Insight)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 25.88 tok/s
- TTFT: 276.44 ms
- Total Duration: 28738.05 ms

## Delta (B - A)
- Throughput Δ: -4.31 tok/s
- TTFT Δ: +127.52 ms (positive = Agent B faster TTFT)
