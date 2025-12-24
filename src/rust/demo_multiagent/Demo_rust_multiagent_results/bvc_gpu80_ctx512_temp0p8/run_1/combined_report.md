# Rust Multi-Agent Report - Run 1

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 14.68s
- Sequential Estimate: 21.54s
- Speedup: 1.47x
- Efficiency: 73.4% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Baseline Collector)
- Base URL: http://localhost:11434
- Config: Ollama defaults
- Throughput: 98.04 tok/s
- TTFT: 11025.64 ms
- Total Duration: 14675.39 ms

## Agent B (Chimera Insight)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 98.39 tok/s
- TTFT: 255.15 ms
- Total Duration: 6866.24 ms

## Delta (B - A)
- Throughput Δ: +0.36 tok/s
- TTFT Δ: +10770.49 ms (positive = Agent B faster TTFT)
