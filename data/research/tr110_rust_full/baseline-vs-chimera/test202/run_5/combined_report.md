# Rust Multi-Agent Report - Run 5

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 60.18s
- Sequential Estimate: 120.27s
- Speedup: 2.00x
- Efficiency: 99.9% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Baseline Collector)
- Base URL: http://localhost:11434
- Config: Ollama defaults
- Throughput: 40.73 tok/s
- TTFT: 879.32 ms
- Total Duration: 60158.55 ms

## Agent B (Chimera Insight)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=512, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 40.65 tok/s
- TTFT: 664.03 ms
- Total Duration: 60073.96 ms

## Delta (B - A)
- Throughput Δ: -0.09 tok/s
- TTFT Δ: +215.29 ms (positive = Agent B faster TTFT)
