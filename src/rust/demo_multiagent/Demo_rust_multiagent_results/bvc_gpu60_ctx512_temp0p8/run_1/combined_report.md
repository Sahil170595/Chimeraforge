# Rust Multi-Agent Report - Run 1

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 15.63s
- Sequential Estimate: 20.26s
- Speedup: 1.30x
- Efficiency: 64.8% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Baseline Collector)
- Base URL: http://localhost:11434
- Config: Ollama defaults
- Throughput: 98.61 tok/s
- TTFT: 251.59 ms
- Total Duration: 4632.94 ms

## Agent B (Chimera Insight)
- Base URL: http://localhost:11434
- Config: num_gpu=60, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 97.21 tok/s
- TTFT: 9475.14 ms
- Total Duration: 15625.16 ms

## Delta (B - A)
- Throughput Δ: -1.40 tok/s
- TTFT Δ: -9223.55 ms (positive = Agent B faster TTFT)
