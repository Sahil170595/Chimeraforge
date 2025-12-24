# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 22.59s
- Sequential Estimate: 42.90s
- Speedup: 1.90x
- Efficiency: 95.0% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://127.0.0.1:11434
- Config: num_gpu=120, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 40.97 tok/s
- TTFT: 7982.01 ms
- Total Duration: 20319.68 ms

## Agent B (Chimera Agent B)
- Base URL: http://127.0.0.1:11435
- Config: num_gpu=120, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 51.59 tok/s
- TTFT: 8012.37 ms
- Total Duration: 22581.84 ms

## Delta (B - A)
- Throughput Δ: +10.62 tok/s
- TTFT Δ: -30.36 ms (positive = Agent B faster TTFT)
