# Rust Multi-Agent Report - Run 1

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 12.48s
- Sequential Estimate: 16.33s
- Speedup: 1.31x
- Efficiency: 65.5% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Baseline Collector)
- Base URL: http://127.0.0.1:11434
- Config: Ollama defaults
- Throughput: 108.77 tok/s
- TTFT: 221.95 ms
- Total Duration: 3859.22 ms

## Agent B (Chimera Insight)
- Base URL: http://127.0.0.1:11435
- Config: num_gpu=80, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 111.82 tok/s
- TTFT: 6361.02 ms
- Total Duration: 12473.63 ms

## Delta (B - A)
- Throughput Δ: +3.06 tok/s
- TTFT Δ: -6139.06 ms (positive = Agent B faster TTFT)
