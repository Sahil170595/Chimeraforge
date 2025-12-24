# Rust Multi-Agent Report - Run 2

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 14.68s
- Sequential Estimate: 21.59s
- Speedup: 1.47x
- Efficiency: 73.5% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Baseline Collector)
- Base URL: http://localhost:11434
- Config: Ollama defaults
- Throughput: 98.86 tok/s
- TTFT: 10721.82 ms
- Total Duration: 14680.47 ms

## Agent B (Chimera Insight)
- Base URL: http://localhost:11434
- Config: num_gpu=60, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 100.07 tok/s
- TTFT: 163.42 ms
- Total Duration: 6913.23 ms

## Delta (B - A)
- Throughput Δ: +1.20 tok/s
- TTFT Δ: +10558.40 ms (positive = Agent B faster TTFT)
