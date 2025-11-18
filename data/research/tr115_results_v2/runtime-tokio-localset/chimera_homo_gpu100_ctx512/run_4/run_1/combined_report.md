# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 53.84s
- Sequential Estimate: 107.24s
- Speedup: 1.99x
- Efficiency: 99.6% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=100, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 40.94 tok/s
- TTFT: 580.23 ms
- Total Duration: 53383.98 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=100, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.52 tok/s
- TTFT: 826.94 ms
- Total Duration: 53821.57 ms

## Delta (B - A)
- Throughput Δ: +0.58 tok/s
- TTFT Δ: -246.71 ms (positive = Agent B faster TTFT)
