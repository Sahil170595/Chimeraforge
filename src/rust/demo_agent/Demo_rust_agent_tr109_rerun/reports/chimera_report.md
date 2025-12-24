# Chimera Agent Report

**Model:** gemma3:latest  
**Runs:** 5  
**Timestamp:** 2025-11-10 04:44:08 UTC  
**Language:** Rust  
**System:** windows (x86_64)

## Configuration

num_gpu=60, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1

## Aggregate Metrics

| Metric | Value |
|--------|-------|
| Average Throughput | 97.96 ± 0.14 tok/s |
| Average TTFT | 1102.39 ± 1665.91 ms |
| Total Tokens Generated | 7891 |
| Average Total Duration | 17239.47 ms |
| Average Prompt Eval Duration | 188.58 ms |
| Average Eval Duration | 16110.54 ms |
| Average Load Duration | 910.63 ms |

## Individual Run Results

| Run | TTFT (ms) | Throughput (tok/s) | Tokens | Duration (ms) |
|-----|-----------|-------------------|--------|---------------|
| 1 | 4082.10 | 97.80 | 1547 | 19960.23 |
| 2 | 373.62 | 97.94 | 1642 | 17160.66 |
| 3 | 330.49 | 98.14 | 1481 | 15441.39 |
| 4 | 391.33 | 98.08 | 1700 | 17736.54 |
| 5 | 334.39 | 97.85 | 1521 | 15898.52 |


## Statistical Summary

- **Throughput CV**: 0.1%
- **TTFT CV**: 151.1%
- **Runs**: 5
