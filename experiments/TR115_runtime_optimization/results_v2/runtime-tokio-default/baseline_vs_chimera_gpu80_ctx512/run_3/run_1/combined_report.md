# Rust Multi-Agent Report - Run 1

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 60.81s
- Sequential Estimate: 121.47s
- Speedup: 2.00x
- Efficiency: 99.9% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Baseline Collector)
- Base URL: http://localhost:11434
- Config: Ollama defaults
- Throughput: 40.07 tok/s
- TTFT: 855.85 ms
- Total Duration: 60638.08 ms

## Agent B (Chimera Insight)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 40.29 tok/s
- TTFT: 790.55 ms
- Total Duration: 60787.88 ms

## Delta (B - A)
- Throughput Δ: +0.22 tok/s
- TTFT Δ: +65.30 ms (positive = Agent B faster TTFT)
