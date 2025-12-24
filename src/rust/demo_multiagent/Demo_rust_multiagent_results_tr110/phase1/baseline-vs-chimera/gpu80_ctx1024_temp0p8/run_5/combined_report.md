# Rust Multi-Agent Report - Run 5

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 14.41s
- Sequential Estimate: 18.92s
- Speedup: 1.31x
- Efficiency: 65.7% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Baseline Collector)
- Base URL: http://localhost:11434
- Config: Ollama defaults
- Throughput: 99.86 tok/s
- TTFT: 215.28 ms
- Total Duration: 4513.96 ms

## Agent B (Chimera Insight)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 99.68 tok/s
- TTFT: 7952.49 ms
- Total Duration: 14409.65 ms

## Delta (B - A)
- Throughput Δ: -0.19 tok/s
- TTFT Δ: -7737.21 ms (positive = Agent B faster TTFT)
