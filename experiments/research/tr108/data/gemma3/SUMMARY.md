# Gemma3 Benchmark Summary

## Quick Stats

| Metric | Value |
|--------|-------|
| **Model** | gemma3:latest |
| **Size** | 3.3 GB |
| **GPU** | NVIDIA RTX 4080 Laptop |
| **Processor** | 100% GPU (confirmed) |
| **Mean Throughput** | 102.85 tokens/s |
| **Mean TTFT** | 0.165 s (warm) |
| **GPU Memory** | 5.3 GB |
| **Test Date** | 2025-10-08 |

## Performance vs Llama3.1

Gemma3 **wins** on all critical gaming metrics:

- **+34% faster** token generation (102.85 vs 76.59 tok/s)
- **-30% smaller** model size (3.3 GB vs 4.7 GB)
- **Lower GPU memory** usage (5.3 GB vs ~6-7 GB)
- **+70% slower** first token (0.165s vs 0.097s) - negligible for gaming

## Best Configuration

```yaml
num_gpu: 999
num_ctx: 4096
temperature: 0.4
```

**Result:** 102.31 tokens/s @ 0.128s TTFT

## Recommendation

**Use Gemma3 for Chimera Heart production**

Gemma3 is the superior choice for real-time gaming banter generation due to significantly faster throughput and smaller footprint. The slightly higher TTFT is not noticeable in gaming scenarios where total response generation time matters more than initial latency.

## Files

- `Gemma3_Benchmark_Report.md` - Full detailed analysis
- `gemma3_baseline.json` - Raw performance data
- `gemma3_param_tuning_summary.csv` - Configuration rankings

**Full documentation:** `docs/Gemma3_Benchmark_Report.md`

