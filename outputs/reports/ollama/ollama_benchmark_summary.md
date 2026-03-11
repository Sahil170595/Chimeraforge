
# Ollama Performance Benchmark Summary ## Baseline (llama3.1:8b-instruct-q4_0)
- Mean generation time across banter scenarios: 5.15 s
- Tokens per second: 7.90
- System utilization snapshot: CPU 13.9% avg / 15.4% peak, GPU util 33% avg / 93% peak
- Detailed exports: baseline_system_metrics.json, baseline_ml_metrics.json, baseline_system_report.txt, baseline_ml_report.txt ## Quantization Sweep
Best throughput achieved with q4_0 at 76.59 tokens/s and TTFT 0.097 s. | tag | mean_tokens_s | median_tokens_s | mean_ttft_s |
| --- | --- | --- | --- |
| q4_0 | 76.59 | 76.88 | 0.097 |
| q5_K_M | 65.18 | 65.03 | 1.354 |
| q8_0 | 46.57 | 46.64 | 2.008 | Plots: artifacts/ollama/quant_tokens_per_sec.png, artifacts/ollama/quant_ttft.png ## Parameter Sweep (using quantization q4_0)
Top configuration: num_gpu=40, num_ctx=1024, temperature=0.4
- Tokens/s: 78.42
- TTFT: 0.088 s Top combinations by throughput: | num_gpu | num_ctx | temperature | mean_tokens_s | mean_ttft_s |
| --- | --- | --- | --- | --- |
| 40.00 | 1024.00 | 0.4 | 78.42 | 0.088 |
| 40.00 | 1024.00 | 0.8 | 78.06 | 0.075 |
| 60.00 | 2048.00 | 0.8 | 78.01 | 0.096 |
| 999.00 | 1024.00 | 0.4 | 77.93 | 0.086 |
| 999.00 | 1024.00 | 0.8 | 77.91 | 0.083 | Additional visuals: artifacts/ollama/param_ttft_vs_tokens.png, heatmaps per temperature in artifacts/ollama/ ## Observations
- q4_0 delivered ~17% higher throughput than q5_K_M and more than 60% gain over q8_0 while keeping TTFT under 0.1 s after warm-up.
- High TTFT outliers correspond to first-run model loads; subsequent calls stabilize below 0.1 s when num_gpu is tuned.
- Lower num_ctx (1024) combined with temperature 0.4-0.8 yields the best throughput; higher contexts increase TTFT with marginal throughput gains.
- Temperature changes had minimal impact on throughput but 0.4 provided the most balanced trade-off between TTFT and deterministic outputs. Generated on 2025-09-30 20:15:45.
