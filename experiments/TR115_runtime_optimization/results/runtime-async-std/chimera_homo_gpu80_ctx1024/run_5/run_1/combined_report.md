# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 10.54s
- Sequential Estimate: 10.54s
- Speedup: 1.00x
- Efficiency: 50.0% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=1024, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 123.12 tok/s
- TTFT: 858.16 ms
- Total Duration: 4440.26 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=1024, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 121.76 tok/s
- TTFT: 589.73 ms
- Total Duration: 6097.47 ms

## Delta (B - A)
- Throughput Δ: -1.36 tok/s
- TTFT Δ: +268.43 ms (positive = Agent B faster TTFT)
