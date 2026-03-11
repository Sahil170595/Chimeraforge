# Technical Report 118: ONNX Runtime + TensorRT Deep Dive


**Version:** 1.0
**Date:** 2025-12-18
**Status:** Draft (auto-generated from artifacts)
**Git SHA:** `4f09b5c5381989515a29b321bcb24d1804e370e2`

## Abstract

TR118 deep-dives ONNX Runtime and TensorRT for local-first LLM inference, closing the TR117 gap where ONNX/TRT runs were fully degraded.
We report performance, degraded-rate, and accuracy (perplexity) gates, using artifact-driven reproducibility (JSONL + CSV + manifests).

## Executive Summary

### Key Findings

- Reliability: 360 run-level records across prefill, generate; degraded-rate = 25.0% (90/360)
- Accuracy: perplexity gate passed (see `C:\Users\sahil\OneDrive\Documents\GitHub\Banterhearts\scripts\tr118\results\tr118v2_crossover\gpt2-5m\processed\perplexity_results.csv`)
- prefill: best mean latency = tensorrt-fp16 (2.48 ms), vs baseline transformers-gpu-compile (19.2 ms, -87.08%)
- generate: best mean latency = onnxruntime-cpu (43.3 ms), vs baseline transformers-gpu-compile (162 ms, -73.34%)
- Note: PyTorch `transformers-gpu-compile` uses `torch.compile(..., backend="cudagraphs", dynamic=False)` on Windows (no Triton).

### Honest Limitations

- `generate` mode is an uncached greedy loop (`use_cache=False`) and is not representative of KV-cached decoding throughput.
- `models/tiny-gpt2` in this repo is a toy/untrained model; perplexity is expected to be near-uniform (~vocab) and accuracy deltas mainly reflect numerical consistency.
- Single model (gpt2/124M) and single machine; results may not generalize to larger models (see TR121).
- Latency excludes end-to-end serving overhead (tokenization, networking, batching policies).

## Introduction

- TR117 established a cross-backend baseline and identified ONNX/TRT infrastructure failures.
- TR118 focuses on making ONNX export + TRT engine builds real and measurable, with explicit degraded reasons and accuracy gates.

## Methodology

### Metrics
- Latency (ms), throughput (tok/s), degraded rate.
- Generation mode (if enabled) uses an uncached greedy loop (repeated full forward passes).

### Accuracy Gate
- Perplexity on WikiText-2 vs PyTorch baseline with per-precision thresholds.

### Statistical Analysis
- 95% confidence intervals + t-tests + Cohen's d via TR117 helpers.

## Experimental Design

- Config: `C:\Users\sahil\OneDrive\Documents\GitHub\Banterhearts\scripts\tr118\results\tr118v2_crossover\gpt2-5m\config_gpt2-5m.yaml`
- Prompt config: `C:\Users\sahil\OneDrive\Documents\GitHub\Banterhearts\scripts\tr117\configs\matrix_tier3.yaml`
- Modes: prefill, generate
- Backends: transformers-gpu-compile, onnxruntime-cpu, onnxruntime-gpu, tensorrt-fp32, tensorrt-fp16, tensorrt-int8
- Scenarios: single_micro, single_short, single_medium, single_long, batch_short, batch_medium
- Repetitions: 5

**Artifacts root:** `C:\Users\sahil\OneDrive\Documents\GitHub\Banterhearts\scripts\tr118\results\tr118v2_crossover\gpt2-5m`

### Run Manifest

- Manifest: `C:\Users\sahil\OneDrive\Documents\GitHub\Banterhearts\scripts\tr118\results\tr118v2_crossover\gpt2-5m\processed\experiment_manifest_1766111615.json`
- Duration (s): 324.87910532951355

## Environment

- OS: Windows-11-10.0.26200-SP0
- Python: 3.13.1 (tags/v3.13.1:0671451, Dec  3 2024, 19:06:28) [MSC v.1942 64 bit (AMD64)]
- GPU: NVIDIA GeForce RTX 4080 Laptop GPU (12282 MB, CC 8.9)
- ONNXRuntime providers: TensorrtExecutionProvider, CUDAExecutionProvider, CPUExecutionProvider
- Key packages: torch=2.8.0+cu128, transformers=4.57.0, onnxruntime=1.23.2, tensorrt=10.12.0.36

## Sanity Checks

### Model / ONNX Artifacts

| Field | Value |
| --- | --- |
| model | C:\Users\sahil\OneDrive\Documents\GitHub\Banterhearts\models\gpt2-5m |
| onnx_path | C:\Users\sahil\OneDrive\Documents\GitHub\Banterhearts\artifacts\tr118v2_crossover\gpt2-5m\onnx\gpt2-5m.onnx |
| onnx_sha256 | 05171a5df30c995e74f7f3c1cba87f05196b4bb696a2642e68f1eb6cdd8c531b |
| onnx_file_size_mb | 34.98 |
| external_data | False |
| external_total_mb | 0 |
| total_artifact_mb | 34.98 |
| initializer_numel_est | 9057280 |
| initializer_bytes_est_mb | 34.55 |
| weight_files_total_mb | 19.23 |

- Weight files: model.safetensors: 19.227127075195312

### TensorRT Engine Inspection

| Precision | Plan_MB | Layers | InspectorType | INT8_in_JSON | INT8_tensors | OutputDTypes | CalibSource | CalibCacheHit |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| fp32 | 57.8 | 901 | dict | False | False | Float=780, Int64=248 | N/A | N/A |
| fp16 | 59.13 | 770 | dict | False | False | Bool=2, Float=315, Half=335, Int64=243 | N/A | N/A |
| int8 | 44.51 | 1025 | dict | False | False | Float=930, Int64=249 | N/A | N/A |

### Perplexity Correctness

| Field | Value |
| --- | --- |
| baseline_ppl | 743.3 |
| baseline_mean_nll | 6.611 |
| baseline_token_count | 72531 |
| ln_vocab | 10.82 |
| expected_uniform_ppl | 5.026e+04 |
| ref_loss_mean_nll | 6.469 |
| ref_loss_ppl | 644.9 |

### Logit Diffs vs PyTorch (Last Token)

| Backend | mean_abs | max_abs | providers_used | error |
| --- | --- | --- | --- | --- |
| onnxruntime-cpu | 9.038e-07 | 3.815e-06 | ['CPUExecutionProvider'] | N/A |
| onnxruntime-gpu | 4.562e-05 | 0.0002654 | ['CUDAExecutionProvider', 'CPUExecutionProvider'] | N/A |
| tensorrt-fp32 | 0.0002355 | 0.001235 | N/A | N/A |
| tensorrt-fp16 | 0.002005 | 0.01178 | N/A | N/A |
| tensorrt-int8 | 2.225e-05 | 0.0003114 | N/A | N/A |

### Sanity Warnings

- TensorRT INT8 engine inspector does not report INT8 coverage; treat INT8 claims as unverified (likely FP16/FP32 fallback).

## Results

### Mode: `prefill`

#### Overall Backend Summary (Run-Level)

| Backend | n_ok | n_total | degraded_rate | lat_mean_ms | lat_ci95 | thr_mean_tok_s | thr_ci95 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| tensorrt-fp16 | 30 | 30 | 0 | 2.478 | [1.767, 3.188] | 1.246e+04 | [1.099e+04, 1.393e+04] |
| tensorrt-fp32 | 30 | 30 | 0 | 2.543 | [2.017, 3.07] | 1.136e+04 | [9637, 1.307e+04] |
| onnxruntime-cpu | 30 | 30 | 0 | 3.633 | [3.16, 4.106] | 7554 | [6215, 8893] |
| tensorrt-int8 | 30 | 30 | 0 | 7.031 | [5.717, 8.345] | 3980 | [3396, 4565] |
| onnxruntime-gpu | 30 | 30 | 0 | 10.3 | [9.894, 10.72] | 2907 | [2094, 3719] |
| transformers-gpu-compile | 30 | 30 | 0 | 19.17 | [17.24, 21.1] | 1484 | [1164, 1803] |

#### Resource Summary (Run-Level)

| Backend | n_ok | gpu_power_mean_w | gpu_mem_peak_mb | gpu_temp_peak_c | cpu_mem_peak_mb |
| --- | --- | --- | --- | --- | --- |
| onnxruntime-cpu | 30 | 2.48 | 824 | 47 | 1629 |
| onnxruntime-gpu | 30 | 3.839 | 854.3 | 47.9 | 1797 |
| tensorrt-fp16 | 30 | 28.14 | 1603 | 49.8 | 2026 |
| tensorrt-fp32 | 30 | 29.72 | 1331 | 49.4 | 1902 |
| tensorrt-int8 | 30 | 7.509 | 1842 | 48.2 | 2061 |
| transformers-gpu-compile | 30 | 3.602 | 730 | 47.53 | 1568 |

- Summary CSV: `C:\Users\sahil\OneDrive\Documents\GitHub\Banterhearts\scripts\tr118\results\tr118v2_crossover\gpt2-5m\processed\latency_summary_prefill.csv`

#### Baseline Comparisons (Overall)

| baseline | candidate | metric | mean_a | mean_b | pct_change | p_value | cohens_d | significant |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| transformers-gpu-compile | onnxruntime-cpu | latency_ms | 19.17 | 3.633 | -81.05 | 6.426e-23 | -4.127 | True |
| transformers-gpu-compile | onnxruntime-gpu | latency_ms | 19.17 | 10.3 | -46.25 | 6.536e-13 | -2.372 | True |
| transformers-gpu-compile | tensorrt-fp16 | latency_ms | 19.17 | 2.478 | -87.08 | 1.077e-23 | -4.285 | True |
| transformers-gpu-compile | tensorrt-fp32 | latency_ms | 19.17 | 2.543 | -86.73 | 3.425e-24 | -4.388 | True |
| transformers-gpu-compile | tensorrt-int8 | latency_ms | 19.17 | 7.031 | -63.32 | 3.055e-15 | -2.745 | True |

#### Figures

![mean_latency_prefill](../../scripts/tr118/results/tr118v2_crossover/gpt2-5m/plots/mean_latency_prefill.png)

![mean_throughput_tok_s_prefill](../../scripts/tr118/results/tr118v2_crossover/gpt2-5m/plots/mean_throughput_tok_s_prefill.png)

![degraded_rate_prefill](../../scripts/tr118/results/tr118v2_crossover/gpt2-5m/plots/degraded_rate_prefill.png)


### Mode: `generate`

#### Overall Backend Summary (Run-Level)

| Backend | n_ok | n_total | degraded_rate | lat_mean_ms | lat_ci95 | thr_mean_tok_s | thr_ci95 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| onnxruntime-cpu | 30 | 30 | 0 | 43.26 | [38.97, 47.56] | 336 | [270.5, 401.6] |
| onnxruntime-gpu | 30 | 30 | 0 | 63.99 | [60.87, 67.1] | 238.4 | [179.2, 297.7] |
| transformers-gpu-compile | 30 | 30 | 0 | 162.3 | [137, 187.6] | 119.4 | [86.3, 152.5] |
| tensorrt-fp16 | 0 | 30 | 1 | N/A | N/A | N/A | N/A |
| tensorrt-fp32 | 0 | 30 | 1 | N/A | N/A | N/A | N/A |
| tensorrt-int8 | 0 | 30 | 1 | N/A | N/A | N/A | N/A |

#### TTFT Summary (Run-Level)

| Backend | n_ok | ttft_mean_ms | ttft_ci95 | ttft_median_ms |
| --- | --- | --- | --- | --- |
| onnxruntime-cpu | 30 | 5.349 | [4.761, 5.937] | 4.843 |
| onnxruntime-gpu | 30 | 8.183 | [7.7, 8.666] | 7.681 |
| transformers-gpu-compile | 30 | 19.98 | [16.81, 23.15] | 20.74 |

#### Resource Summary (Run-Level)

| Backend | n_ok | gpu_power_mean_w | gpu_mem_peak_mb | gpu_temp_peak_c | cpu_mem_peak_mb |
| --- | --- | --- | --- | --- | --- |
| onnxruntime-cpu | 30 | 7.78 | 928 | 49 | 1603 |
| onnxruntime-gpu | 30 | 13.93 | 938 | 49.27 | 1813 |
| transformers-gpu-compile | 30 | 13.65 | 800 | 49.33 | 1497 |

- Summary CSV: `C:\Users\sahil\OneDrive\Documents\GitHub\Banterhearts\scripts\tr118\results\tr118v2_crossover\gpt2-5m\processed\latency_summary_generate.csv`

#### Baseline Comparisons (Overall)

| baseline | candidate | metric | mean_a | mean_b | pct_change | p_value | cohens_d | significant |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| transformers-gpu-compile | onnxruntime-cpu | latency_ms | 162.3 | 43.26 | -73.34 | 2.101e-13 | -2.45 | True |
| transformers-gpu-compile | onnxruntime-gpu | latency_ms | 162.3 | 63.99 | -60.57 | 9.435e-11 | -2.037 | True |

#### Figures

![mean_latency_generate](../../scripts/tr118/results/tr118v2_crossover/gpt2-5m/plots/mean_latency_generate.png)

![mean_throughput_tok_s_generate](../../scripts/tr118/results/tr118v2_crossover/gpt2-5m/plots/mean_throughput_tok_s_generate.png)

![degraded_rate_generate](../../scripts/tr118/results/tr118v2_crossover/gpt2-5m/plots/degraded_rate_generate.png)

### Accuracy (Perplexity Gate)

- Results CSV: `C:\Users\sahil\OneDrive\Documents\GitHub\Banterhearts\scripts\tr118\results\tr118v2_crossover\gpt2-5m\processed\perplexity_results.csv`
- Diagnostics JSON: `C:\Users\sahil\OneDrive\Documents\GitHub\Banterhearts\scripts\tr118\results\tr118v2_crossover\gpt2-5m\processed\perplexity_results.json`

| Backend | PPL | delta_frac | Threshold | Pass | Error |
| --- | --- | --- | --- | --- | --- |
| transformers-gpu-compile | 743.3 | 0 | nan | True | N/A |
| onnxruntime-cpu | 743.3 | -6.101e-09 | 0.001 | True | N/A |
| onnxruntime-gpu | 743.3 | -4.686e-06 | 0.001 | True | N/A |
| tensorrt-fp32 | 743.3 | -6.298e-06 | 0.001 | True | N/A |
| tensorrt-fp16 | 743.3 | -6.44e-06 | 0.005 | True | N/A |
| tensorrt-int8 | 743.3 | -6.44e-06 | 0.02 | True | N/A |

### Export Overhead (ONNX)

| Field | Value |
| --- | --- |
| onnx_path | C:\Users\sahil\OneDrive\Documents\GitHub\Banterhearts\artifacts\tr118v2_crossover\gpt2-5m\onnx\gpt2-5m.onnx |
| export_time_s | N/A |
| file_size_mb | 34.98 |
| opset_version | 17 |
| dynamic_axes | True |
| trt_friendly_inputs | True |
| reused | True |
| valid | N/A |
| onnx_sha256 | 05171a5df30c995e74f7f3c1cba87f05196b4bb696a2642e68f1eb6cdd8c531b |

### TensorRT Build Overhead

- Build metadata: `C:\Users\sahil\OneDrive\Documents\GitHub\Banterhearts\scripts\tr118\results\tr118v2_crossover\gpt2-5m\processed\trt_build_metadata_1766111615.json`

| Precision | Plan | Built | Reused | Build s | Size MB | Dynamic | Profiles | Error |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| fp32 | gpt2-5m_fp32.plan | False | True | N/A | 57.8 | True | 5 | N/A |
| fp16 | gpt2-5m_fp16.plan | False | True | N/A | 59.13 | True | 5 | N/A |
| int8 | gpt2-5m_int8.plan | False | True | N/A | 44.51 | True | 5 | N/A |

## Discussion

### Interpretation
- This run demonstrates that ONNX export + TensorRT engine builds can be made reliable on a single Windows + CUDA workstation.
- For this tiny model and short prompts, ORT-CPU can win on latency due to reduced GPU launch/dispatch overhead; larger models should re-test (TR121).
- TensorRT build cost is non-trivial; treat it as an offline step that must be amortized for production value.

### Limitations / Threats to Validity
- See `Executive Summary: Honest Limitations` for the primary caveats.

## Conclusions

TR118 provides an artifact-driven pipeline for measuring ONNX Runtime and TensorRT locally, including degraded-rate accounting, build/export metadata, and perplexity gates.

## Recommendations

- If you need portability/simplicity: start with ONNX Runtime (CPU or CUDA EP).
- If you can prebuild engines and need maximum GPU throughput: TensorRT (FP16/INT8 as permitted by accuracy gates).
- Keep PyTorch as the reference baseline; on Windows prefer `torch.compile(..., backend="cudagraphs", dynamic=False)` for stability.

## Reproducibility

Run the full pipeline:

```bash
python scripts/tr118/run_experiment.py --config C:\Users\sahil\OneDrive\Documents\GitHub\Banterhearts\scripts\tr118\results\tr118v2_crossover\gpt2-5m\config_gpt2-5m.yaml --device cuda
```

Generate this report from artifacts:

```bash
python scripts/tr118/generate_report.py --config C:\Users\sahil\OneDrive\Documents\GitHub\Banterhearts\scripts\tr118\results\tr118v2_crossover\gpt2-5m\config_gpt2-5m.yaml --manifest C:\Users\sahil\OneDrive\Documents\GitHub\Banterhearts\scripts\tr118\results\tr118v2_crossover\gpt2-5m\processed\experiment_manifest_1766111615.json
```

## Appendix

- Artifacts root: `C:\Users\sahil\OneDrive\Documents\GitHub\Banterhearts\scripts\tr118\results\tr118v2_crossover\gpt2-5m`
- Processed dir: `C:\Users\sahil\OneDrive\Documents\GitHub\Banterhearts\scripts\tr118\results\tr118v2_crossover\gpt2-5m\processed`
