# TR109/TR112 Validation Summary

- Rust configs analysed: **19** (baseline + chimera per config)
- Rust baseline throughput avg: **114.38 tok/s**
- Max rust baseline throughput: **114.98 tok/s**
- Python chimera throughput avg: **0.00 tok/s** (peak **0.00 tok/s**)

## Sample Entries
- `baseline_default` (rust_baseline) -> runs=6, avg throughput 114.54 tok/s, avg TTFT 603.5 ms
- `baseline_default` (rust_chimera) -> runs=6, avg throughput 114.68 tok/s, avg TTFT 547.3 ms
- `gpu120_ctx1024_temp0p6` (rust_baseline) -> runs=6, avg throughput 114.05 tok/s, avg TTFT 1328.7 ms

## Python Sweep Samples
- `run_gpu120_ctx1024_temp0p6` -> runs=1, avg throughput 0.00 tok/s, avg TTFT 0.0 ms
- `run_gpu120_ctx1024_temp0p8` -> runs=1, avg throughput 0.00 tok/s, avg TTFT 0.0 ms
- `run_gpu120_ctx256_temp0p6` -> runs=1, avg throughput 0.00 tok/s, avg TTFT 0.0 ms