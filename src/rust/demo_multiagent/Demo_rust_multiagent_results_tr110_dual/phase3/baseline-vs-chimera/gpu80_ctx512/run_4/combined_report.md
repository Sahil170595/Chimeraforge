# Rust Multi-Agent Report - Run 4

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 4.89s
- Sequential Estimate: 6.42s
- Speedup: 1.31x
- Efficiency: 65.7% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Baseline Collector)
- Base URL: http://127.0.0.1:11434
- Config: Ollama defaults
- Throughput: 93.48 tok/s
- TTFT: 271.58 ms
- Total Duration: 4886.52 ms

## Agent B (Chimera Insight)
- Base URL: http://127.0.0.1:11435
- Config: num_gpu=80, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 42.20 tok/s
- TTFT: 310.84 ms
- Total Duration: 1533.05 ms

## Delta (B - A)
- Throughput Δ: -51.28 tok/s
- TTFT Δ: -39.26 ms (positive = Agent B faster TTFT)
