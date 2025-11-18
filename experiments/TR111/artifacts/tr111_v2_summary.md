# TR111_v2 Sweep Summary

- Configurations parsed: **19**
- Baseline throughput: **98.74 tok/s avg** | peak **99.53 tok/s**
- Chimera throughput: **98.87 tok/s avg** | peak **99.50 tok/s**

## Top 5 Configurations by Chimera Throughput

- `gpu80_ctx512_temp0p8` -> **99.50 tok/s**, delta throughput +0.19%, TTFT 3679 ms
- `gpu80_ctx256_temp0p6` -> **99.47 tok/s**, delta throughput +0.38%, TTFT 3717 ms
- `gpu80_ctx256_temp0p8` -> **99.43 tok/s**, delta throughput +0.57%, TTFT 3674 ms
- `gpu120_ctx1024_temp0p8` -> **99.41 tok/s**, delta throughput +0.19%, TTFT 3514 ms
- `gpu80_ctx512_temp0p6` -> **99.27 tok/s**, delta throughput -0.26%, TTFT 3721 ms

## Notes
- All configs currently have a single recorded run (stddev = 0).
- Source folders: `Demo_rust_agent\Demo_rust_agent_sweep`