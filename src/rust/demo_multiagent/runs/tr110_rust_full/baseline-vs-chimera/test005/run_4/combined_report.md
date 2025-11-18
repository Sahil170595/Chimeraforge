# Rust Multi-Agent Report - Run 4

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 244.30s
- Sequential Estimate: 301.56s
- Speedup: 1.23x
- Efficiency: 61.7% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Baseline Collector)
- Base URL: http://localhost:11434
- Config: Ollama defaults
- Throughput: 20.57 tok/s
- TTFT: 875.13 ms
- Total Duration: 244263.49 ms

## Agent B (Chimera Insight)
- Base URL: http://localhost:11435
- Config: num_gpu=120, num_ctx=512, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 40.53 tok/s
- TTFT: 640.77 ms
- Total Duration: 57236.24 ms

## Delta (B - A)
- Throughput Δ: +19.95 tok/s
- TTFT Δ: +234.36 ms (positive = Agent B faster TTFT)
