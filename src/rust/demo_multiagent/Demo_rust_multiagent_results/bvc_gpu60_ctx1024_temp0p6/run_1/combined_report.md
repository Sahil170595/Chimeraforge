# Rust Multi-Agent Report - Run 1

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 18.76s
- Sequential Estimate: 26.75s
- Speedup: 1.43x
- Efficiency: 71.3% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Baseline Collector)
- Base URL: http://localhost:11434
- Config: Ollama defaults
- Throughput: 97.34 tok/s
- TTFT: 4355.59 ms
- Total Duration: 7992.49 ms

## Agent B (Chimera Insight)
- Base URL: http://localhost:11434
- Config: num_gpu=60, num_ctx=1024, temp=0.6, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 98.58 tok/s
- TTFT: 12148.21 ms
- Total Duration: 18761.66 ms

## Delta (B - A)
- Throughput Δ: +1.24 tok/s
- TTFT Δ: -7792.62 ms (positive = Agent B faster TTFT)
