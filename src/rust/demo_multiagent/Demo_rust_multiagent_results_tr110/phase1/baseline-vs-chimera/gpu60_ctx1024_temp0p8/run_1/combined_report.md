# Rust Multi-Agent Report - Run 1

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 13.94s
- Sequential Estimate: 17.91s
- Speedup: 1.29x
- Efficiency: 64.3% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Baseline Collector)
- Base URL: http://localhost:11434
- Config: Ollama defaults
- Throughput: 100.35 tok/s
- TTFT: 195.50 ms
- Total Duration: 3974.21 ms

## Agent B (Chimera Insight)
- Base URL: http://localhost:11434
- Config: num_gpu=60, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 101.05 tok/s
- TTFT: 7638.76 ms
- Total Duration: 13939.23 ms

## Delta (B - A)
- Throughput Δ: +0.70 tok/s
- TTFT Δ: -7443.26 ms (positive = Agent B faster TTFT)
