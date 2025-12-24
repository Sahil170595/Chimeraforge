# Rust Multi-Agent Report - Run 4

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 11.79s
- Sequential Estimate: 21.45s
- Speedup: 1.82x
- Efficiency: 91.0% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Baseline Collector)
- Base URL: http://127.0.0.1:11434
- Config: Ollama defaults
- Throughput: 42.01 tok/s
- TTFT: 204.31 ms
- Total Duration: 9660.93 ms

## Agent B (Chimera Insight)
- Base URL: http://127.0.0.1:11435
- Config: num_gpu=60, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 53.45 tok/s
- TTFT: 352.57 ms
- Total Duration: 11790.04 ms

## Delta (B - A)
- Throughput Δ: +11.44 tok/s
- TTFT Δ: -148.26 ms (positive = Agent B faster TTFT)
