# Rust Multi-Agent Report - Run 1

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 48.38s
- Sequential Estimate: 48.38s
- Speedup: 1.00x
- Efficiency: 50.0% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Baseline Collector)
- Base URL: http://localhost:11434
- Config: Ollama defaults
- Throughput: 106.83 tok/s
- TTFT: 683.42 ms
- Total Duration: 24798.54 ms

## Agent B (Chimera Insight)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 108.05 tok/s
- TTFT: 589.98 ms
- Total Duration: 23516.71 ms

## Delta (B - A)
- Throughput Δ: +1.22 tok/s
- TTFT Δ: +93.44 ms (positive = Agent B faster TTFT)
