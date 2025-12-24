# Rust Multi-Agent Report - Run 1

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 10.40s
- Sequential Estimate: 10.40s
- Speedup: 1.00x
- Efficiency: 50.0% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Baseline Collector)
- Base URL: http://localhost:11434
- Config: Ollama defaults
- Throughput: 122.94 tok/s
- TTFT: 846.45 ms
- Total Duration: 4130.16 ms

## Agent B (Chimera Insight)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 121.22 tok/s
- TTFT: 595.96 ms
- Total Duration: 6268.58 ms

## Delta (B - A)
- Throughput Δ: -1.72 tok/s
- TTFT Δ: +250.49 ms (positive = Agent B faster TTFT)
